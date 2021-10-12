"""
Test bot.py
"""

# pylint: disable=import-error,redefined-outer-name

import pytest

from bot import MusicBot


@pytest.fixture
def bot():
    """ Get a bot.MusicBot instance """
    return MusicBot()


def test_initialization(bot):
    """ Test the bot is initialized """
    assert bot
