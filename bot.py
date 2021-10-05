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

    client = discord.Client()

    @client.event
    async def on_ready(self):
        """ Login and loading handling """
        logging.info("we have logged in as %s", self.user)

    @client.event
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
        config.read(".env")
        token = config['SECRETS']['TOKEN']

    logging.info("Starting bot")
    MusicBot().run(token)
