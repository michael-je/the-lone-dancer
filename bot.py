"""
Author MikkMakk88, morgaesis et al.

(c)2021
"""

import os
import configparser
import logging

import discord  # pylint: disable=import-error


class MusicBot(discord.Client):
    """
    The main bot functionality
    """

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
        if message.content.startswith('!hello'):
            await message.channel.send('Hello!')


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
