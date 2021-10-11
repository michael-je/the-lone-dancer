"""
Author MikkMakk88, morgaesis et al.

(c)2021
"""

import os
import configparser
import logging
import time

import discord  # pylint: disable=import-error
import jokeapi  # pylint: disable=import-error


async def bot_joke(msg, joke_pause=3):
    """
    Reply to the author with joke from Sv443's Joke API

    If the joke is two-parter wait `joke_pause` seconds between setup and
    delivery.
    """
    logging.info("Making jokes: %s", msg)
    content = msg.content
    argv = [] if len(content.split()) < 2 else content.split()[1:]

    valid_categories = [
        "any",
        "misc",
        "programming",
        "dark",
        "pun",
        "spooky",
        "christmas",
    ]
    # Setup complete

    # User asks for help
    if "help" in argv or "-h" in argv or "--help" in argv:
        await msg.channel.send("I see you asked for help!")
        await msg.channel.send("You can ask for the following categories:")
        await msg.channel.send(f"{', '.join(valid_categories)}")
        return

    # User asks for categories
    categories = [cat.lower() for cat in argv]
    invalid_categories = set(argv) - set(categories)
    category_plurality = (
        "categories" if len(invalid_categories) > 1 else "category"
    )
    if len(invalid_categories) > 0:
        await msg.channel.send(
            f"Invalid joke {category_plurality} '{invalid_categories}'"
        )
        logging.info(
            "User %s requested invalid joke category %s",
            msg.author,
            invalid_categories,
        )
        return

    # Get the joke
    jokes = jokeapi.Jokes()
    joke = jokes.get_joke(lang="en", category=categories)
    logging.info(
        "User %s requested joke of category %s", msg.author, categories
    )
    logging.info("The joke is: %s", joke)

    # Joke can be one-liner or has setup
    if joke["type"] == "single":
        await msg.channel.send(joke["joke"])
    else:
        await msg.channel.send(joke["setup"])
        time.sleep(joke_pause)
        await msg.channel.send(joke["delivery"])


class MusicBot(discord.Client):
    """
    The main bot functionality
    """

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
        if message.content.startswith("!hello"):
            await message.channel.send("Hello!")
        if message.content.startswith("!joke"):
            await bot_joke(message)


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
