"""
Test bot.py
"""

# pylint: disable=import-error,redefined-outer-name

import pytest

from bot import BotDispatcher


@pytest.fixture
def bot():
    """Get a bot.MusicBot instance"""
    return BotDispatcher()


def test_initialization(bot):
    """Test the bot is initialized"""
    assert bot
