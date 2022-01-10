"""
Serves a bot on Discord for playing music in voice chat, as well as some fun additions.
"""
# pylint: disable=import-error
# pylint: disable=no-self-use
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-locals
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments
# pylint: disable=too-many-lines


import os
import re
import logging
import asyncio
import collections
import traceback
import time
import argparse
import abc

import discord
import jokeapi
import youtubesearchpython
import pytube
import spotipy

import pafy_fixed.pafy_fixed as pafy

LOG_FMT = (
    "%(asctime)s - "
    "%(levelname)-5s - "
    "%(name)-20s - "
    "line %(lineno)4s in %(funcName)-20s - "
    "%(message)s"
)


class SongList:
    """
    Class for lazily getting PaFy data from spotify title and artist, while
    having length
    """

    def __init__(self, tracks, get_media):
        self.tracks = tracks
        self.get_media = get_media
        self.index = 0

    def __len__(self):
        return len(self.tracks)

    def __iter__(self):
        return self

    @abc.abstractmethod
    def fetch(self, track):
        """Fetch/load track from some source"""
        raise NotImplementedError

    def __getitem__(self, index):
        logging.info(
            "Fetching DIRECTLY item at index %d/%d", self.index, len(self.tracks)
        )
        return self.fetch(self.tracks[index])

    def __next__(self):
        logging.info("Fetching NEXT item at index %d/%d", self.index, len(self.tracks))
        if self.index >= len(self.tracks):
            raise StopIteration
        track = self.tracks[self.index]
        self.index += 1
        return self.fetch(track)


class SpotifyList(SongList):
    """Implementation of Songlist for Spotify"""

    # pylint: disable=too-few-public-methods
    def fetch(self, track):
        title = track["name"]
        artist = track["artists"][0]["name"]
        assert isinstance(title, str)
        assert isinstance(artist, str)
        youtube_track = self.get_media(f"{title} - {artist}")
        logging.info(
            "Lazily fetched '%s - %s' %d/%d",
            title,
            artist,
            self.index,
            len(self.tracks),
        )
        return youtube_track


class YouTubeList(SongList):
    """Implementation of Songlist for Youtube playlists"""

    # pylint: disable=too-few-public-methods

    def fetch(self, track):
        youtube_track = self.get_media(track)
        logging.info(
            "Lazily fetched '%s' %d/%d",
            youtube_track.title,
            self.index,
            len(self.tracks),
        )
        return youtube_track


class BotDispatcher(discord.Client):
    """
    Dispatcher for client instances
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clients = {}  # guild -> discord.Client instance

    async def on_ready(self):
        """
        Login and loading handling
        """
        logging.info("we have logged in as %s", self.user)

    async def on_message(self, message):
        """
        Login and loading handling
        """
        if message.guild not in self.clients:
            self.clients[message.guild] = MusicBot(message.guild, self.loop, self.user)
        await self.clients[message.guild].handle_message(message)

    async def on_error(
        self, event_name, *args, **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Notify user of error and log it
        """
        if event_name == "on_message":
            message = args[0]
            logging.error("Event name: %s", event_name)
            logging.error("args: %s", args)
            logging.error("kwargs: %s", kwargs)
            print(traceback.format_exc())
            await message.channel.send(":robot: Something came up!")


class AfterInterrupt:
    """
    Class for continuing playback after interrupt
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, voice_client, source, after_callback, stack):
        self.voice_client = voice_client
        self.source = source
        self.after_callback = after_callback
        self.stack = stack
        self.stack.append(self)

    def __call__(self, *_args):
        if self.source:
            after = self.after_callback
            if len(self.stack) > 0:
                after = self.stack.pop()
            self.voice_client.play(self.source, after=after)


class MusicBot:
    """
    The main bot functionality
    """

    COMMAND_PREFIX = "-"
    REACTION_EMOJI = "👍"
    DOCS_URL = "www.github.com/michael-je/the-lone-dancer"
    DISCONNECT_TIMER_SECONDS = 600
    TEXTWIDTH = 60
    SYNTAX_LANGUAGE = "arm"
    N_PLAYLIST_SHOW = 10

    END_OF_QUEUE_MSG = ":sparkles: End of queue"

    def __init__(self, guild, loop, dispatcher_user):
        self.guild = guild
        self.loop = loop
        self.dispatcher_user = dispatcher_user

        self.handlers = {}
        self.help_messages = {}
        self.media_deque = collections.deque()
        self.voice_client = None
        self.current_media = None
        self.last_text_channel = None
        self.last_played_time = None
        self.continue_adding_to_playlist = None

        self.url_regex = re.compile(
            r"http[s]?://"
            r"(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )
        self.playlist_regex = re.compile(r"\b(?:play)?list(/|\=(\w+))")
        self.youtube_playlist_regex = re.compile(
            r"^https://(www\.)?youtu(be\.com|.be)/(playlist|watch\?v\=\w+&list\=)"
        )
        self.spotify_regex = re.compile(r"^https?://(\w+\.)*spotify.com")
        self.spotify_playlist_regex = re.compile(
            r"^https?://(\w+\.)*spotify.com/playlist"
        )
        self.spotify_album_regex = re.compile(r"^https?://(\w+\.)*spotify.com/album")
        self.spotify_track_regex = re.compile(r"^https?://(\w+\.)*spotify.com/track")

        # Boolean to control whether the after callback is called
        self.after_callback_blocked = False

        # This lock should be acquired before trying to change the voice state of the
        # bot
        self.command_lock = asyncio.Lock()
        self.interrupt_play_stack = collections.deque()

        self.spotify = self.get_spotify_client()
        self.register_command(
            "play",
            help_message="Play audio from URL",
            handler=self.play,
            # guarded_by=self.command_lock,
            argument_name="term/url",
        )
        self.register_command(
            "cancel",
            help_message="Stop a playlist from fetching more songs",
            handler=self.cancel,
            # guarded_by=self.command_lock,
            argument_name="term/url",
        )
        self.register_command(
            "playnext",
            help_message="Put a song at the front of the queue",
            handler=self.play_next,
            # guarded_by=self.command_lock,
            argument_name="term/url",
        )
        self.register_command(
            "stop",
            help_message="Stop and remove current song from queue",
            handler=self.stop,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "pause",
            help_message="Pause current song",
            handler=self.pause,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "resume",
            help_message="Resume current song",
            handler=self.resume,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "skip",
            help_message="Skip to next song",
            handler=self.skip,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "next",
            help_message="Skip to next song",
            handler=self.skip,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "disconnect",
            help_message="Disconnect from the current voice client",
            handler=self.disconnect,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "clear",
            help_message="Clear the current queue",
            handler=self.clear_queue,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "remove",
            help_message="Remove Nth, first, or last song from the queue",
            handler=self.remove_song_from_deque,
            guarded_by=self.command_lock,
            argument_name="position",
        )
        self.register_command(
            "queue",
            help_message="Show the current queue",
            handler=self.show_queue,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "nowplaying",
            help_message="Show the currently playing song",
            handler=self.show_current,
        )
        self.register_command(
            "source",
            help_message="Show the link to the currently playing song",
            handler=self.show_source,
        )
        self.register_command(
            "help",
            help_message="Show this help message or help for given command",
            handler=self.show_help,
            argument_name="command",
        )
        self.register_command(
            "move",
            help_message="Move the bot to your voice channel",
            handler=self.move,
            guarded_by=self.command_lock,
        )

        self.register_command(
            "hello",
            help_message="Say hello",
            handler=self.hello,
        )
        self.register_command(
            "countdown",
            help_message="Count down from 10 and explode",
            handler=self.countdown,
        )
        self.register_command(
            "dinkster",
            help_message="Ring the dinkster in your voice channel",
            handler=self.dinkster,
            guarded_by=self.command_lock,
        )
        self.register_command(
            "joke",
            help_message="Tell a joke",
            handler=self.joke,
        )

    def register_command(
        self,
        command_name,
        help_message: str,
        handler=None,
        guarded_by: asyncio.Lock = None,
        argument_name: str = "",
    ):
        """
        Register a command with the name 'command_name'.

        Arguments:
          command_name: String. The name of the command to register. This is
            what users should use to run the command.
          handler: A function. This function should accept two arguments:
            discord.Message and a string. The messageris the message being
            processed by the handler and command_content is the string
            contents of the command passed by the user.
          guarded_by: A lock which will be acquired before each call to the
            handler passed.
          help_message: A string describing how to use the given handler.
            Maximum 100 characters.
          argument_name: Name of argument used in help message.
             Requires length command_name+argument_name+3 < 21
        """
        assert handler
        assert command_name not in self.handlers
        assert len(help_message) < 100
        assert len(command_name) + len(argument_name) + 3 < 21

        if len(argument_name) > 0:
            argument_name = f"<{argument_name}>"
        help_prefix = f"{self.COMMAND_PREFIX}{command_name} {argument_name}"
        help_prefix = f"{help_prefix:<21}"

        self.help_messages[command_name] = f"{help_prefix}{help_message}"

        if guarded_by:

            async def guarded_handler(*args):
                async with guarded_by:
                    return await handler(*args)

            self.handlers[command_name] = guarded_handler
        else:
            self.handlers[command_name] = handler

    def get_command_handler(self, message_content):
        """
        Tries to parse message_content as a command and fetch the corresponding
        handler for the command.

        Arguments
        ---------
        message_content : discord.message
            Contents of the message to parse. Assumed to start with COMMAND_PREFIX.

        Returns
        -------
        handler : function
            Function to handle the command.

        command_content : discord.message
            The message contents with the prefix and command named stripped.

        error_msg : str
            String or None. If not None it signals that the command was unknown. The
            value will be an error message displayable to the user which says the
            command was not recognized.
        """
        if not message_content.startswith(self.COMMAND_PREFIX):
            raise ValueError(
                f"Message '{message_content}' does not begin with"
                f" '{MusicBot.COMMAND_PREFIX}'"
            )

        prefix_end = len(self.COMMAND_PREFIX)
        content_split = message_content[prefix_end:].split(" ", 1)
        command_name = content_split[0]
        command_content = ""
        if len(content_split) == 2:
            command_content = content_split[1]

        if command_name not in self.handlers:
            return None, None, f"Command {command_name} not recognized."

        return self.handlers[command_name], command_content, None

    async def handle_message(self, message):
        """
        Handler for receiving messages
        """
        self.last_text_channel = message.channel
        if message.author == self.dispatcher_user:
            return

        if not message.content:
            return

        if not message.content.startswith(self.COMMAND_PREFIX):
            # Message not attempting to be a command.
            return

        handler, command_content, error_msg = self.get_command_handler(message.content)

        # The command was not recognized
        if error_msg:
            return await message.channel.send(f":robot: {error_msg}")

        # Execute the command.
        await handler(message, command_content)

    def get_spotify_client(self):
        """Get Spotify client"""
        try:
            creds = spotipy.oauth2.SpotifyClientCredentials()
        except spotipy.SpotifyOauthError:
            logging.warning(
                "No spotipy credentials found. Running without spotify capabilities."
            )
            return None
        return spotipy.Spotify(auth_manager=creds)

    def after_callback(self, _):
        """
        Plays the next item in queue if after_callback_blocked == False, otherwise stops
        the music. Used as a callback for play().
        """
        if not self.after_callback_blocked:
            self.loop.create_task(self.attempt_disconnect())
            self.loop.create_task(self.next_in_queue())
        else:
            self.after_callback_blocked = False

    def _stop(self):
        """
        A helper function that stops playing music
        """
        self.after_callback_blocked = True
        self.voice_client.stop()
        if len(self.media_deque) == 0:
            self.current_media = None

    def create_audio_source(self, audio_url):
        """Creates an audio sorce from an audio url"""
        return discord.FFmpegPCMAudio(audio_url)

    async def next_in_queue(self):
        """
        Switch to next song in queue
        """
        if not self.voice_client:
            logging.error(
                "Should not be called when the bot is not connected to voice!"
            )

        if len(self.media_deque) == 0:
            self.current_media = None
            self.voice_client.stop()
            return

        media, message = self.media_deque.popleft()

        logging.info("Fetching audio URL for '%s'", media.title)
        self.current_media = media
        if media.duration == "00:00:00":
            self.loop.create_task(
                message.channel.send("Sorry, I can't play livestreams :sob:")
            )
            await self.next_in_queue()
            return

        audio_url = media.getbestaudio().url
        audio_source = self.create_audio_source(audio_url)

        if self.voice_client.is_playing():
            self._stop()

        logging.info("Playing audio source")
        self.voice_client.play(audio_source, after=self.after_callback)
        logging.info("Audio source started")

        await message.channel.send(
            f":notes: Now Playing :notes:\n```\n{media.title}\n```"
        )

    async def create_or_get_voice_client(self, message):
        """Get a voice client to play audio.

        Arguments:
          message: A Discord message.

        Returns:
          A Discord VoiceClient. If the bot is already connected to a channel,
          return that voice client. If not, join the requesting user's voice
          channel, if they are connected to one.
        """
        # Already connected to a voice channel, no need to create a new client.
        if self.voice_client:
            return self.voice_client

        requesting_user = message.author
        if not requesting_user.voice or not requesting_user.voice.channel:
            logging.info("User %s not in a voice channel", message.author)
            await message.channel.send(
                f":studio_microphone: {requesting_user}, "
                + "please join a voice channel to start the :robot:"
            )
            return None

        # Create a new voice client.
        logging.info("Connecting to voice channel %s", message.author.voice.channel)
        self.voice_client = await requesting_user.voice.channel.connect()
        logging.info("Connected to voice channel for user %s", message.author)
        await self.voice_client.guild.change_voice_state(
            channel=requesting_user.voice.channel, self_deaf=True
        )
        logging.info("Deafened bot")

        return self.voice_client

    def pafy_search(self, youtube_link_or_id):
        """Search for youtube link with pafy"""
        media = pafy.new(youtube_link_or_id)
        if media.dislikes == 0:
            logging.info("Ignoring dislike count in new media")

        return media

    def youtube_search(self, search_str):
        """Search for search_str on youtube"""
        return youtubesearchpython.VideosSearch(search_str).result()

    async def attempt_disconnect(self):
        """
        Should be called whenever a song finishes playing, or when media is paused or
        stopped. Attempts to disconnect the voice client after a set amount of time by
        checking whether anything is currently playing.
        """
        logging.info(
            "Will attempt to disconnect in %s seconds",
            MusicBot.DISCONNECT_TIMER_SECONDS,
        )
        self.last_played_time = time.time()
        await asyncio.sleep(MusicBot.DISCONNECT_TIMER_SECONDS)

        if self.voice_client.is_playing():
            return

        if time.time() - self.last_played_time < self.DISCONNECT_TIMER_SECONDS:
            return
        logging.info("Disconnecting from voice chat due to inactivity")

        self._stop()
        await self.voice_client.disconnect()
        self.voice_client = None

    async def notify_if_voice_client_is_missing(self, message):
        """
        Returns True and notifies the user if a voice_client hasn't been created yet
        """
        if not self.voice_client:
            logging.info(
                "User %s asked for media action, but nothing is playing", message.author
            )
            await message.channel.send(":kissing_heart: Start playing something first")
            return True
        return False

    def get_media(self, search_term):
        """
        Fetches youtube result for link or search term and returns the pafy media
        instance.
        """
        media = None
        try:
            url = self.url_regex.search(search_term)
            if url:
                logging.info("Fetching video metadata with pafy")
                media = self.pafy_search(url.group())
            else:
                logging.info("Fetching search results with pafy")
                search_result = self.youtube_search(search_term)
                media = self.pafy_search(search_result["result"][0]["id"])
        except KeyError as err:
            # In rare cases we get an error processing media, e.g. when vid has no likes
            # KeyError: 'like_count'
            logging.error(err)

        return media

    def _get_spotify_tracks(self, url):
        """
        Fetch list of spotify tracks in album/playlist or single track

        Each returned track is a dictionary of title, artist, length
        """
        if self.spotify is None:
            logging.error(
                "Spotify capabilities not enabled. See docs to enable spotify"
            )
            return None
        tracks = []
        if re.search(self.spotify_track_regex, url):
            tracks.append(self.spotify.track(url))

        if re.search(self.spotify_album_regex, url):
            tracks = self.spotify.album(url)["tracks"]["items"]

        if re.search(self.spotify_playlist_regex, url):
            tracks = [
                item["track"] for item in self.spotify.playlist(url)["tracks"]["items"]
            ]

        return SpotifyList(tracks, self.get_media)

    def pytube_playlist(self, url):
        """Get playlist info from pytube"""
        return pytube.Playlist(url)

    def _get_youtube_tracks(self, url):
        """
        Fetch list of youtube tracks in playlist
        """
        links = None
        if re.search(self.playlist_regex, url):
            # Get list of URLs to individual videos in playlist
            links = self.pytube_playlist(url)
        else:
            links = [url]

        return YouTubeList(links, self.get_media)

    async def cancel(self, message, _command_content):
        """Stop adding new songs to queue"""
        self.continue_adding_to_playlist = False
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def playlist(self, message, command_content):
        """Play a playlist, youtube, or spotify"""
        logging.info("Fetching playlist for user %s", message.author)
        playlist = None
        self.continue_adding_to_playlist = True
        if re.search(self.spotify_regex, command_content):
            playlist = self._get_spotify_tracks(command_content)
        elif re.search(self.youtube_playlist_regex, command_content):
            playlist = self._get_youtube_tracks(command_content)

        if playlist is None:
            await message.add_reaction("👎")
            await message.channel.send(":robot: Unable to fetch playlist :worried:")
            return

        await message.add_reaction(MusicBot.REACTION_EMOJI)
        added = []
        n_failed = 0
        progress = 0
        total = len(playlist)
        status_fmt = "Fetching playlist... {}"
        reply = await message.channel.send(status_fmt.format(""))
        for media in playlist:
            if not self.continue_adding_to_playlist:
                break
            await reply.edit(content=status_fmt.format(f"{progress/total:.0%}"))
            progress += 1
            self.media_deque.append((media, message))
            logging.info("Added song '%s' from playlist", media.title)
            added.append(media)
            if len(added) == 1 and not self.voice_client.is_playing():
                await self.next_in_queue()
        logging.info("%d items added to queue, %d failed", len(added), n_failed)

        final_status = ""
        final_status += f":clipboard: Added {len(added)} of "
        final_status += f"{len(added)+n_failed} songs to queue :notes:\n"
        final_status += f"```{self.SYNTAX_LANGUAGE}"
        final_status += "\n"
        for media in added[: self.N_PLAYLIST_SHOW]:
            title = media.title
            titlewidth = self.TEXTWIDTH - 10
            if len(title) > titlewidth:
                title = title[: titlewidth - 3] + "..."

            duration_m = int(media.duration[:2]) * 60 + int(media.duration[3:5])
            duration_s = int(media.duration[6:])
            duration = f"({duration_m}:{duration_s:0>2})"
            # Time: 5-6 char + () + buffer = 10
            final_status += f"{title:<{titlewidth}}{duration:>10}"
            final_status += "\n"
        if len(added) >= self.N_PLAYLIST_SHOW:
            final_status += "...\n"
        final_status += "```"

        logging.debug("final status message: \n%s", final_status)

        await reply.edit(content=final_status)

    async def play_empty(self, message, command_content):
        """
        Play/resume depending on queue status
        """
        if self.voice_client.is_paused():
            await self.resume(message, command_content)
        elif not self.voice_client.is_playing() and len(self.media_deque) != 0:
            await self.resume(message, command_content)
        elif self.voice_client.is_playing():
            logging.info("User %s tried 'play' with no search term", message.author)
            await message.channel.send(":unamused: Please enter something to search!")
        else:
            logging.info("User %s tried 'play' on empty queue", message.author)
            await message.channel.send(
                ":unamused: Queue is empty - please enter something to search!"
            )

    async def play_single(self, message, command_content, playnext):
        """
        Play a single youtube or spotify track
        """

        # Single track/url/search term
        media = None
        if re.search(self.spotify_track_regex, command_content):
            # Since _get_spotify_tracks returns a list of all songs in the spotify link
            # the list will be 1-long, and only contain the requested song.
            media = self._get_spotify_tracks(command_content)[0]
        else:
            # Same here, but for youtube tracks.
            media = self._get_youtube_tracks(command_content)[0]

        if media is None:
            await message.channel.send(":robot: Error getting media data :robot:")
            return

        logging.debug("Media found:\n%s", media)

        if playnext:
            self.media_deque.appendleft((media, message))
        else:
            self.media_deque.append((media, message))

        voice_client = await self.create_or_get_voice_client(message)
        if voice_client.is_playing():
            logging.info("Added '%s' to queue", media.title)
            await message.channel.send(
                f":clipboard: Added to Queue\n```\n{media.title}\n```"
            )
        else:
            logging.info("Playing media")
            await self.next_in_queue()

    async def play(self, message, command_content, playnext=False):
        """
        Play URL or first search term from command_content in the author's voice channel
        """
        voice_client = await self.create_or_get_voice_client(message)
        if not voice_client:
            return

        # Empty play command
        if not command_content:
            self.play_empty(message, command_content)
            return

        # Playlist/album
        if (
            re.search(self.playlist_regex, command_content)
            or re.search(self.spotify_album_regex, command_content)
            or re.search(self.spotify_playlist_regex, command_content)
        ):
            await self.playlist(message, command_content)
            return

        await self.play_single(message, command_content, playnext)

    async def play_next(self, message, command_content):
        """
        Like play, but puts the song at the front of the queue.
        """
        await self.play(message, command_content, playnext=True)

    async def stop(self, message, _command_content):
        """
        Stop currently playing song
        """
        if await self.notify_if_voice_client_is_missing(message):
            return
        if len(self.media_deque) == 0 and not self.voice_client.is_playing():
            logging.info("User %s stopped on empty non-playing queue", message.author)
            await message.channel.send(MusicBot.END_OF_QUEUE_MSG)
            return

        self._stop()
        logging.info("Stopped media for user %s", message.author)
        self.loop.create_task(self.attempt_disconnect())
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def pause(self, message, _command_content):
        """
        Pause currently playing song
        """
        if await self.notify_if_voice_client_is_missing(message):
            return
        if not self.voice_client.is_playing():
            logging.info(
                "User %s tried 'pause' when nothing is playing", message.author
            )
            await message.channel.send(
                ":face_with_raised_eyebrow: Nothing is playing..."
            )
            return

        self.voice_client.pause()
        logging.info("Paused media for user %s", message.author)
        self.loop.create_task(self.attempt_disconnect())
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def resume(self, message, _command_content):
        """
        Resume playing current song
        """
        if await self.notify_if_voice_client_is_missing(message):
            return
        if len(self.media_deque) == 0 and not self.voice_client.is_paused():
            logging.info(
                "User %s requested 'resume' but queue is empty", message.author
            )
            await message.channel.send(MusicBot.END_OF_QUEUE_MSG)
            return
        if self.voice_client.is_playing():
            logging.info(
                "User %s requested 'resume' something is already playing",
                message.author,
            )
            await message.channel.send(
                ":face_with_raised_eyebrow: Song currently playing"
            )
            return

        if self.voice_client.is_paused():
            logging.info("Resuming for user %s", message.author)
            self.voice_client.resume()
        elif not self.voice_client.is_playing():
            logging.info("Resuming for user %s (next_in_queue)", message.author)
            await self.next_in_queue()
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def skip(self, message, _command_content):
        """
        Skip to next song in queue
        """
        if await self.notify_if_voice_client_is_missing(message):
            return

        if len(self.media_deque) == 0:
            await message.channel.send(MusicBot.END_OF_QUEUE_MSG)
            self._stop()
        else:
            await self.next_in_queue()
            await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def clear_queue(self, message, _command_content):
        """
        Stop current song and remove everything from queue
        """
        while len(self.media_deque) != 0:
            self.media_deque.popleft()

        self._stop()
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def remove_song_from_deque(self, message, command_content):
        """
        Removes a specific song from the queue, based on its position therein
        """
        if len(self.media_deque) == 0:
            await message.channel.send(":unamused: The queue is empty...")
            return

        arg = command_content.split(maxsplit=1)[0]

        range_regex = re.compile(r"(\d+)-(\d+)")
        range_regex_match = range_regex.match(arg)
        if range_regex_match:
            await self.remove_range_from_deque(message, range_regex_match)
            return

        if arg.lower() == "first":
            song_index = 0
        elif arg.lower() == "last":
            song_index = -1
        elif arg.isnumeric():
            song_index = int(arg) - 1
        else:
            await message.channel.send(
                f"{arg} isn't a valid song position/range :open_mouth:"
            )
            return

        if song_index < -1 or song_index >= len(self.media_deque):
            await message.channel.send(
                "Pick something *in* the queue! :face_with_symbols_over_mouth:"
            )
            return

        del self.media_deque[song_index]
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def remove_range_from_deque(self, message, range_regex_match):
        """
        Receives a match regex and uses its 2 capture groups to remove a range of songs
        from the queue.
        """
        range1 = int(range_regex_match.group(1))
        range2 = int(range_regex_match.group(2))
        range_start = min(range1, range2)
        range_end = max(range1, range2)

        if range_start < 1 or range_end > len(self.media_deque):
            await message.channel.send(
                f"{range_regex_match.group(0)} isn't a valid range :open_mouth:"
            )
            return

        n_songs_to_remove = range_end - range_start + 1
        for _ in range(n_songs_to_remove):
            del self.media_deque[range_start - 1]

        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def show_current(self, message, _command_content):
        """
        Displays the currently playing song
        """
        if self.current_media is None and len(self.media_deque) == 0:
            await message.channel.send(":sparkles: Nothing in queue")
            return

        reply = ""
        reply += ":notes: Now playing :notes:\n"
        reply += "```\n"
        reply += f"{self.current_media.title}\n"
        reply += "```"
        await message.channel.send(reply)

    async def show_queue(self, message, _command_content):
        """
        Displays media that has been queued
        """
        await self.show_current(message, _command_content)

        reply = "```\n"
        if len(self.media_deque) == 0:
            reply += " -- No audio in queue --\n"
        else:
            reply += " -- Queue --\n"

        for index, item in enumerate(self.media_deque):
            media, _ = item  # we only care about the media metadata
            reply += str(index + 1) + ": " + media.title
            reply += "\n"
        reply += "```"

        await message.channel.send(reply)

    async def move(self, message, _command_content):
        """
        Moves the bot to the voice channel that the message author is currently
        connected to.
        """
        if await self.notify_if_voice_client_is_missing(message):
            return

        if not message.author.voice:
            await message.channel.send(":thinking: You're not in a voice channel")
            return

        if message.author.voice.channel == self.voice_client.channel:
            await message.channel.send(
                ":relieved: Bot is already in your voice channel"
            )
            return

        await self.voice_client.move_to(message.author.voice.channel)
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def show_help(self, message, command_content):
        """
        Show link to full documentation
        """
        reply = "```\n"
        if len(command_content) > 0:
            reply += self.help_messages[command_content]
        else:
            for _, help_message in sorted(self.help_messages.items()):
                reply += f"{help_message}\n"
        reply += "```\n"
        reply += f"For full documentation: `{self.DOCS_URL}`"
        await message.channel.send(reply)

    async def show_source(self, message, _command_content):
        """
        Show the link to the currently playing media
        """
        await message.channel.send(f"https://youtu.be/{self.current_media.videoid}")

    async def disconnect(self, message, _command_content):
        """Disconnects the bot from the voice channel its connected to, if any."""
        if self.voice_client:
            self._stop()
            await self.voice_client.disconnect()
            self.voice_client = None
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def hello(self, message, _command_content):
        """
        Greet the author with a nice message
        """
        await message.channel.send(f":wave: Hello! {message.author}")

    async def countdown(self, message, command_content):
        """
        Count down from 10 and explode
        """
        try:
            seconds = int(command_content)
            while seconds > 0:
                await message.channel.send(seconds)
                await asyncio.sleep(1)
                seconds -= 1
            await message.channel.send(":boom: BOOOM!!! :boom:")
        except ValueError:
            await message.channel.send(f":robot: {command_content} is not an integer.")

    async def interrupt_play(self, message, source):
        """
        Pause currently playing audio c (if any), play source s, then resume c
        """
        voice_client = await self.create_or_get_voice_client(message)
        if not voice_client:
            return

        current_source = voice_client.source
        voice_client.pause()
        voice_client.play(
            source,
            after=AfterInterrupt(
                voice_client,
                current_source,
                self.after_callback,
                self.interrupt_play_stack,
            ),
        )
        return True

    async def dinkster(self, message, _command_content):
        """
        Ring the dinkster in the currently connected voice channel or
        connect to the voice channel of the requesting user.
        """
        dinkster_source = await discord.FFmpegOpusAudio.from_probe("Dinkster.ogg")
        if await self.interrupt_play(message, dinkster_source):
            await message.add_reaction("🤠")

    async def joke(self, message, command_content, joke_pause=3):
        """
        Reply to the author with joke from Sv443's Joke API

        If the joke is two-parter wait `joke_pause` seconds between setup and
        delivery.
        """
        logging.info("Making jokes: %s", message.content)
        argv = command_content.split()

        valid_categories = set(
            [
                "any",
                "misc",
                "programming",
                "dark",
                "pun",
                "spooky",
                "christmas",
            ]
        )
        # Setup complete

        # User asks for help
        if "help" in argv or "-h" in argv or "--help" in argv:
            await message.channel.send("I see you asked for help!")
            await message.channel.send("You can ask for the following categories:")
            await message.channel.send(f"{', '.join(valid_categories)}")
            return

        # User asks for categories
        categories = set(cat.lower() for cat in argv)
        invalid_categories = categories - valid_categories
        logging.info("Invalid categories: %s", invalid_categories)
        category_plurality = "categories" if len(invalid_categories) > 1 else "category"
        if len(invalid_categories) > 0:
            await message.channel.send(
                f":interrobang: Invalid joke {category_plurality} "
                f"'{', '.join(invalid_categories)}'"
            )
            logging.info(
                "User %s requested invalid joke category %s",
                message.author,
                invalid_categories,
            )
            return

        # Get the joke
        jokes = jokeapi.Jokes()
        joke = jokes.get_joke(lang="en", category=categories)
        logging.info(
            "User %s requested joke of category %s", message.author, categories
        )
        logging.info("The joke is: %s", joke)

        # Joke can be one-liner or has setup
        if joke["type"] == "single":
            await message.channel.send(joke["joke"])
        else:
            await message.channel.send(joke["setup"])
            await asyncio.sleep(joke_pause)
            await message.channel.send(joke["delivery"])


def parse():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="This is The Lone Dancer")
    parser.add_argument(
        "-v",
        "--verbose",
        dest="v",
        action="count",
        default=0,
        help="Increase verbosity, defaulting to WARNING, then for each 'v' added "
        "increases to INFO then DEBUG; see --quiet for ERROR loglevel",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Log only errors (ERROR loglevel)"
    )
    parser.add_argument("--log-file", help="Path to logfile, if any")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="File containing discord token",
    )
    parser.add_argument(
        "--token",
        help="Discord token for bot; use --env-file if possible instead",
    )
    return parser.parse_args()


if __name__ == "__main__":
    print("Starting Discord bot")
    cli = parse()
    log_level = logging.WARNING - cli.v * 10  # make warning the default
    if cli.quiet:
        log_level = logging.ERROR  # pylint: disable=invalid-name
    logging.basicConfig(
        filename=cli.log_file,
        filemode="w+",
        level=log_level,
        format=LOG_FMT,
    )

    token = os.getenv("DISCORD_TOKEN")
    if cli.token is not None:
        token = cli.token
    if token is None:
        with open(cli.env_file, "r", encoding="utf-8") as env_file:
            for line in env_file.readlines():
                match = re.search(r"^DISCORD_TOKEN=(.*)", line)
                if match is not None:
                    logging.info("Found token in file '%s'", cli.env_file)
                    token = match.group(1).strip()
    assert token is not None

    logging.info("Starting bot")
    BotDispatcher().run(token)
