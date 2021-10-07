"""
Author MikkMakk88, morgaesis et al.

(c)2021
"""

import os
import configparser
import logging
import asyncio

import discord  # pylint: disable=import-error


class MusicBot(discord.Client):
    """
    The main bot functionality
    """

    def __init__(self):
        self.handlers = {}

        self.register_command("hello", handler = self.hello)
        self.register_command("countdown", handler = self.countdown)
        self.register_command("dinkster", handler = self.dinkster)

        super().__init__()

    def register_command(self, command_name, handler = None):
        assert(handler)
        self.handlers[command_name] = handler

    def get_handler_if_command(self, message_content):
        if not message_content or message_content[0] != "!":
            return None, None, None

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
                audio_source = await discord.FFmpegOpusAudio.from_probe("Dinkster.ogg")
                voice_client.play(audio_source)
                await asyncio.sleep(10)
                await voice_client.disconnect()

    _discord_helper = discord.Client()

    @_discord_helper.event
    async def on_ready(self):
        """ Login and loading handling """
        logging.info("we have logged in as %s", self.user)

    @_discord_helper.event
    async def on_message(self, message):
        """ Handler for receiving messages """
        if message.author == self.user:
            return

        handler, command_content, error_msg = self.get_handler_if_command(message.content)

        # There was an error during command parsing.
        if error_msg:
            return await message.channel.send(error_msg)

        # This message was not attempting to be a command.
        if not handler:
            return

        # Execute the command.
        await handler(message, command_content)


if __name__ == '__main__':
    print("Starting Discord bot")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    token = os.getenv('TOKEN')
    if token is None:
        config = configparser.ConfigParser()
        config.read("bot.conf")
        token = config['secrets']['TOKEN']

    logging.info("Starting bot")
    MusicBot().run(token)
