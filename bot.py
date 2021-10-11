"""
Author MikkMakk88, morgaesis et al.

(c)2021
"""

import os
import configparser
import logging
import asyncio

import discord  # pylint: disable=import-error
import jokeapi  # pylint: disable=import-error


class MusicBot(discord.Client):
    """
    The main bot functionality
    """

    COMMAND_PREFIX = "!"

    def __init__(self):
        self.handlers = {}

        self.register_command("hello", handler=self.hello)
        self.register_command("countdown", handler=self.countdown)
        self.register_command("dinkster", handler=self.dinkster)
        self.register_command("joke", handler=self.joke)

        super().__init__()

    def register_command(self, command_name, handler=None):
        """Register a command with the name 'command_name'.

        Arguments:
          command_name: String. The name of the command to register. This is
            what users should use to run the command.
          handler: A function. This function should accept two arguments:
            discord.Message and a string. The messageris the message being
            processed by the handler and command_content is the string
            contents of the command passed by the user.
        """
        assert handler
        assert command_name not in self.handlers
        self.handlers[command_name] = handler

    def get_command_handler(self, message_content):
        """Tries to parse message_content as a command and fetch the corresponding handler for the command.

        Arguments:
          message_content: Contents of the message to parse. Assumed to start with COMMAND_PREFIX.

        Returns:
          handler: Function to handle the command.
          command_content: The message contents with the prefix and command named stripped.
          error_msg: String or None. If not None it signals that the command was
            unknown. The value will be an error message displayable to the user which
            says the command was not recognized.
        """
        if message_content[0] != "!":
            raise ValueError(
                f"Message '{message_content}' does not begin with '{MusicBot.COMMAND_PREFIX}'"
            )

        content_split = message_content[1:].split(" ", 1)
        command_name = content_split[0]
        command_content = ""
        if len(content_split) == 2:
            command_content = content_split[1]

        if command_name not in self.handlers:
            return None, None, f"Command {command_name} not recognized."

        return self.handlers[command_name], command_content, None

    async def hello(self, message, command_content):
        await message.channel.send("Hello!")

    async def countdown(self, message, command_content):
        try:
            seconds = int(command_content)
            while seconds > 0:
                await message.channel.send(seconds)
                await asyncio.sleep(1)
                seconds -= 1
            await message.channel.send("BOOOM!!!")
        except ValueError:
            await message.channel.send(f"{command_content} is not an integer.")

    async def dinkster(self, message, command_content):
        for channel in await message.guild.fetch_channels():
            if isinstance(channel, discord.VoiceChannel):
                voice_client = await channel.connect()
                audio_source = await discord.FFmpegOpusAudio.from_probe(
                    "Dinkster.ogg"
                )
                voice_client.play(audio_source)
                await asyncio.sleep(10)
                await voice_client.disconnect()

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
        category_plurality = (
            "categories" if len(invalid_categories) > 1 else "category"
        )
        if len(invalid_categories) > 0:
            await message.channel.send(
                f"Invalid joke {category_plurality} "
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

    _discord_helper = discord.Client()

    @_discord_helper.event
    async def on_ready(self):
        """Login and loading handling"""
        logging.info("we have logged in as %s", self.user)

    @_discord_helper.event
    async def on_message(self, message):
        """Handler for receiving messages"""
        if message.author == self.user:
            return

        if not message.content:
            return

        if message.content[0] != MusicBot.COMMAND_PREFIX:
            # Message not attempting to be a command.
            return

        handler, command_content, error_msg = self.get_command_handler(
            message.content
        )

        # The command was not recognized
        if error_msg:
            return await message.channel.send(error_msg)

        # Execute the command.
        await handler(message, command_content)


if __name__ == "__main__":
    print("Starting Discord bot")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    token = os.getenv("TOKEN")
    if token is None:
        config = configparser.ConfigParser()
        config.read("bot.conf")
        token = config["secrets"]["TOKEN"]

    logging.info("Starting bot")
    MusicBot().run(token)
