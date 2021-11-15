# pylint: disable=import-error
# pylint: disable=missing-module-docstring


import os
import re
import logging
import asyncio
import queue
import traceback

import discord
import jokeapi
import pafy
from youtubesearchpython import VideosSearch


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


class MusicBot:
    """
    The main bot functionality
    """

    # pylint: disable=no-self-use
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods

    COMMAND_PREFIX = "-"
    REACTION_EMOJI = "👍"
    DOCS_URL = "github.com/michael-je/the-lone-dancer"

    END_OF_QUEUE_MSG = ":sparkles: End of queue"

    def __init__(self, guild, loop, dispatcher_user):
        self.guild = guild
        self.loop = loop
        self.dispatcher_user = dispatcher_user

        self.handlers = {}
        self.help_messages = {}
        self.media_queue = queue.Queue()
        self.voice_client = None
        self.current_media = None
        self.last_text_channel = None

        self.url_regex = re.compile(
            r"http[s]?://"
            r"(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )

        # Boolean to control whether the after callback is called
        self.after_callback_blocked = False

        # This lock should be acquired before trying to change the voice state of the
        # bot
        self.command_lock = asyncio.Lock()

        self.register_command(
            "play",
            handler=self.play,
            guarded_by=self.command_lock,
            help_message="Play audio from URL",
            argument_name="term/url",
        )
        self.register_command(
            "stop",
            handler=self.stop,
            guarded_by=self.command_lock,
            help_message="Stop and remove current song from queue",
        )
        self.register_command(
            "pause",
            handler=self.pause,
            guarded_by=self.command_lock,
            help_message="Pause current song",
        )
        self.register_command(
            "resume",
            handler=self.resume,
            guarded_by=self.command_lock,
            help_message="Resume current song",
        )
        self.register_command(
            "skip",
            handler=self.skip,
            guarded_by=self.command_lock,
            help_message="Skip to next song",
        )
        self.register_command(
            "next",
            handler=self.skip,
            guarded_by=self.command_lock,
            help_message="Skip to next song",
        )
        self.register_command(
            "disconnect",
            handler=self.disconnect,
            guarded_by=self.command_lock,
            help_message="Disconnect from the current voice client",
        )
        self.register_command(
            "clear",
            handler=self.clear_queue,
            guarded_by=self.command_lock,
            help_message="Clear the current queue",
        )
        self.register_command(
            "queue",
            handler=self.show_queue,
            guarded_by=self.command_lock,
            help_message="Show the current queue",
        )
        self.register_command(
            "nowplaying",
            handler=self.show_current,
            help_message="Show the currently playing song",
        )
        self.register_command(
            "source",
            handler=self.show_source,
            help_message="Show the link to the currently playing song",
        )
        self.register_command(
            "help",
            handler=self.show_help,
            help_message="Show this help message or help for given command",
            argument_name="command",
        )

        self.register_command("hello", handler=self.hello, help_message="Say hello")
        self.register_command(
            "countdown",
            handler=self.countdown,
            help_message="Count down from 10 and explode",
        )
        self.register_command(
            "dinkster",
            handler=self.dinkster,
            guarded_by=self.command_lock,
            help_message="Ring the dinkster in your voice channel",
        )
        self.register_command("joke", handler=self.joke, help_message="Tell a joke")

    def register_command(  # pylint: disable=too-many-arguments
        self,
        command_name,
        handler=None,
        guarded_by: asyncio.Lock = None,
        help_message: str = "",
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
             Requires length command_name+argument_name+3 < 20
        """
        assert handler
        assert command_name not in self.handlers
        assert len(help_message) < 100
        assert len(command_name) + len(argument_name) + 3 < 20

        if len(argument_name) > 0:
            argument_name = f"<{argument_name}>"
        help_prefix = f"{self.COMMAND_PREFIX}{command_name} {argument_name}"
        help_prefix = f"{help_prefix:<20}"

        self.help_messages[command_name] = f"{help_prefix}{help_message}"

        if guarded_by:

            async def guarded_handler(*args):
                logging.info("Aquiring lock")
                async with guarded_by:
                    return await handler(*args)
                logging.info("Releasing lock")

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
            self.next_in_queue()
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

    def next_in_queue(self):
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

        self.loop.create_task(
            message.channel.send(
                f":notes: Now Playing :notes:\n```\n{media.title}\n```"
            )
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

    async def play(self, message, command_content):
        """
        Play URL or first search term from command_content in the author's voice channel
        """
        voice_client = await self.create_or_get_voice_client(message)
        if not voice_client:
            return

        if not command_content:
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

        media = None
        try:
            if self.url_regex.match(command_content):
                logging.info("Fetching video metadata with pafy")
                media = pafy.new(command_content)
            else:
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
            self.next_in_queue()

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
            self.next_in_queue()
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
            self.next_in_queue()
            await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def clear_queue(self, message, _command_content):
        """
        Stop current song and remove everything from queue
        """
        while not self.media_queue.empty():
            self.media_queue.get()

        self._stop()
        await message.add_reaction(MusicBot.REACTION_EMOJI)

    async def show_current(self, message, _command_content):
        """
        Displays the currently playing song
        """
        if self.current_media is None and self.media_queue.empty():
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
            await self.voice_client.disconnect()
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

    async def dinkster(self, message, _command_content):
        """
        Ring the dinkster in the currently connected voice channel or
        connect to the voice channel of the requesting user.
        """
        audio_source = await discord.FFmpegOpusAudio.from_probe("Dinkster.ogg")
        (await self.create_or_get_voice_client(message)).play(audio_source)

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
