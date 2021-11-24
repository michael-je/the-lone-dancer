# pylint: disable=import-error
# pylint: disable=missing-module-docstring


import os
import re
import logging
import asyncio
import collections
import queue
import traceback

import discord
import jokeapi
import pafy
from youtubesearchpython import VideosSearch
import pytube


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
    ):  # pylint: disable=arguments-differ,no-self-use
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

    # pylint: disable=no-self-use
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    COMMAND_PREFIX = "-"
    REACTION_EMOJI = "👍"
    TEXTWIDTH = 60
    SYNTAX_LANGUAGE = "arm"

    END_OF_QUEUE_MSG = ":sparkles: End of queue"

    def __init__(self, guild, loop, dispatcher_user):
        self.guild = guild
        self.loop = loop
        self.dispatcher_user = dispatcher_user

        self.handlers = {}
        self.media_queue = queue.Queue()
        self.voice_client = None
        self.current_media = None
        self.last_text_channel = None

        self.url_regex = re.compile(
            r"http[s]?://"
            r"(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )
        self.playlist_regex = re.compile(r"\b(?:play)?list\b\=(\w+)")

        # Boolean to control whether the after callback is called
        self.after_callback_blocked = False

        # This lock should be acquired before trying to change the voice state of the
        # bot
        self.command_lock = asyncio.Lock()
        self.interrupt_play_stack = collections.deque()

        self.register_command("play", handler=self.play, guarded_by=self.command_lock)
        self.register_command("stop", handler=self.stop, guarded_by=self.command_lock)
        self.register_command("pause", handler=self.pause, guarded_by=self.command_lock)
        self.register_command(
            "resume", handler=self.resume, guarded_by=self.command_lock
        )
        self.register_command("skip", handler=self.skip, guarded_by=self.command_lock)
        self.register_command(
            "disconnect", handler=self.disconnect, guarded_by=self.command_lock
        )
        self.register_command(
            "queue", handler=self.show_queue, guarded_by=self.command_lock
        )
        self.register_command("move", handler=self.move, guarded_by=self.command_lock)

        self.register_command("hello", handler=self.hello)
        self.register_command("countdown", handler=self.countdown)
        self.register_command(
            "dinkster", handler=self.dinkster, guarded_by=self.command_lock
        )
        self.register_command("joke", handler=self.joke)

    def register_command(
        self, command_name, handler=None, guarded_by: asyncio.Lock = None
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
        """
        assert handler
        assert command_name not in self.handlers

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

    def after_callback(self, _):
        """
        Plays the next item in queue if after_callback_blocked == False, otherwise stops
        the music. Used as a callback for play().
        """
        if not self.after_callback_blocked:
            # we could self.loop.create_task here if next_in_queue needs to be async
            self.loop.create_task(self.next_in_queue())
        else:
            self.after_callback_blocked = False

    def _stop(self):
        """
        A helper function that stops playing music
        """
        self.after_callback_blocked = True
        self.voice_client.stop()

        if self.media_queue.empty():
            self.current_media = None

    async def next_in_queue(self):
        """
        Switch to next song in queue
        """
        if not self.voice_client:
            logging.error(
                "Should not be called when the bot is not connected to voice!"
            )

        if self.media_queue.empty():
            self.current_media = None
            self.voice_client.stop()
            return

        media, message = self.media_queue.get()

        logging.info("Fetching audio URL for '%s'", media.title)
        self.current_media = media
        audio_url = media.getbestaudio().url
        audio_source = discord.FFmpegPCMAudio(audio_url)

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

    async def playlist(self, message, command_content):
        """Play a playlist"""
        logging.info("Fetching playlist for user %s", message.author)
        playlist = pytube.Playlist(command_content)
        await message.add_reaction(MusicBot.REACTION_EMOJI)
        added = []
        n_failed = 0
        progress = 0
        total = len(playlist)
        status_fmt = "Fetching playlist... {}"
        reply = await message.channel.send(status_fmt.format(""))
        for video in playlist:
            await reply.edit(content=status_fmt.format(f"{progress/total:.0%}"))
            progress += 1
            try:
                media = pafy.new(video)
            except KeyError as err:
                logging.error(err)
                n_failed += 1
                continue
            self.media_queue.put((media, message))
            added.append(media)
            if len(added) == 1 and not self.voice_client.is_playing():
                await self.next_in_queue()
        logging.info("%d items added to queue, %d failed", len(added), n_failed)

        final_status = ""
        final_status += f":clipboard: Added {len(added)} of "
        final_status += f"{len(added)+n_failed} songs to queue :notes:\n"
        final_status += f"```{self.SYNTAX_LANGUAGE}"
        final_status += "\n"
        for media in added[:10]:
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
        if len(added) >= 10:
            final_status += "...\n"
        final_status += "```"

        logging.info("final status message: \n%s", final_status)

        await reply.edit(content=final_status)

    async def play(self, message, command_content):
        """
        Play URL or first search term from command_content in the author's voice channel
        """
        voice_client = await self.create_or_get_voice_client(message)
        if not voice_client:
            return

        if not command_content:
            # No search term/url
            if self.voice_client.is_paused():
                await self.resume(message, command_content)
            elif not self.voice_client.is_playing() and not self.media_queue.empty():
                await self.resume(message, command_content)
            elif self.voice_client.is_playing():
                logging.info("User %s tried 'play' with no search term", message.author)
                await message.channel.send(
                    ":unamused: Please enter something to search!"
                )
            else:
                logging.info("User %s tried 'play' on empty queue", message.author)
                await message.channel.send(
                    ":unamused: Queue is empty - please enter something to search!"
                )
            return

        if re.findall(self.playlist_regex, command_content):
            await self.playlist(message, command_content)
            return

        media = None
        try:
            if self.url_regex.match(command_content):
                # url to video
                logging.info("Fetching video metadata with pafy")
                media = pafy.new(command_content)
            else:
                # search term
                logging.info("Fetching search results with pafy")
                search_result = VideosSearch(command_content).result()
                media = pafy.new(search_result["result"][0]["id"])
        except KeyError as err:
            # In rare cases we get an error processing media, e.g. when vid has no likes
            # KeyError: 'like_count'
            logging.error(err)
            await message.channel.send(":robot: Error getting media data :robot:")

        logging.info("Media found:\n%s", media)

        # We queue up a pair of the media metadata and the message context, so we can
        # continue to message the channel that this command was instanciated from as the
        # queue is unrolled.
        self.media_queue.put((media, message))

        if voice_client.is_playing():
            logging.info("Added media to queue")
            await message.channel.send(
                f":clipboard: Added to Queue\n```\n{media.title}\n```"
            )
        else:
            logging.info("Playing media")
            await self.next_in_queue()

    async def stop(self, message, _command_content):
        """
        Stop currently playing song
        """
        if await self.notify_if_voice_client_is_missing(message):
            return
        if self.media_queue.empty() and not self.voice_client.is_playing():
            logging.info("User %s stopped on empty non-playing queue", message.author)
            await message.channel.send(MusicBot.END_OF_QUEUE_MSG)
            return

        self._stop()
        logging.info("Stopped media for user %s", message.author)
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
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def resume(self, message, _command_content):
        """
        Resume playing current song
        """
        if await self.notify_if_voice_client_is_missing(message):
            return
        if self.media_queue.empty() and not self.voice_client.is_paused():
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

        if self.media_queue.empty():
            await message.channel.send(MusicBot.END_OF_QUEUE_MSG)
            self._stop()
        else:
            await self.next_in_queue()
            await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def show_queue(self, message, _command_content):
        """
        Displays media that has been queued
        """
        if self.current_media is None and self.media_queue.empty():
            await message.channel.send(":sparkles: Nothing in queue")
            return

        reply = ""
        reply += ":notes: Now playing :notes:\n"
        reply += "\n```"
        reply += f"{self.current_media.title}\n"
        if self.media_queue.empty():
            reply += " -- No audio in queue --\n"
        else:
            reply += " -- Queue --\n"

        for index, item in enumerate(self.media_queue.queue):  # Internals usage :(
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


if __name__ == "__main__":
    print("Starting Discord bot")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # pylint: disable=invalid-name
    token = os.getenv("DISCORD_TOKEN")
    if token is None:
        with open(".env", "r", encoding="utf-8") as env_file:
            for line in env_file.readlines():
                match = re.search(r"^DISCORD_TOKEN=(.*)", line)
                if match is not None:
                    logging.info("Found token in file '.env'")
                    token = match.group(1).strip()
    assert token is not None

    logging.info("Starting bot")
    BotDispatcher().run(token)
