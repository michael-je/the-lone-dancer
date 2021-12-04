# pylint: disable=missing-function-docstring
# pylint: disable=missing-module-docstring

from unittest import mock
import asyncio
import unittest
import bot


class MockVoiceClient:
    """The mock version of a Discord VoiceClient"""

    def __init__(self):
        self.after_callback = None
        self.current_audio_source = None
        self.guild = mock.AsyncMock()

    def is_playing(self):
        return self.current_audio_source is not None

    def play(self, audio_source, after=None):
        # Play should not be called something was already playing.
        assert not self.current_audio_source
        self.current_audio_source = audio_source
        self.after_callback = after

    def stop(self):
        self.current_audio_source = None
        if self.after_callback is not None:
            self.after_callback(None)
        self.after_callback = None

    def finish_audio_source(self, exception=None):
        """Call this to signal that the audio source has finished"""
        self.after_callback(exception)
        self.current_audio_source = None


def create_mock_voice_channel():
    voice_client = MockVoiceClient()
    voice_channel = mock.Mock()
    voice_channel.connect = mock.AsyncMock(return_value=voice_client)

    return voice_channel


def create_mock_voice_state(channel=None):
    voice_state = mock.Mock()
    voice_state.channel = channel
    return voice_state


def create_mock_author(name="default_author", voice_state=None):
    author = mock.Mock()
    author.author_str = name

    def author_eq(self, other_author):
        return self.author_str == other_author.author_str

    author.__eq__ = author_eq

    def author_repr(self):
        return self.author_str

    author.__repr__ = author_repr

    author.voice = voice_state

    return author


def create_mock_message(
    contents="",
    author=create_mock_author(name="default_user"),
):
    message = mock.Mock()
    message.content = contents
    message.author = author
    message.channel.send = mock.AsyncMock()

    return message


class MusicBotTest(unittest.IsolatedAsyncioTestCase):
    """MusicBot test suite"""

    async def asyncSetUp(self):
        # pylint: disable=attribute-defined-outside-init

        self.dispatcher_ = mock.Mock()
        self.dispatcher_.user = create_mock_author(name="test_bot")
        self.dispatcher_.loop = asyncio.get_running_loop()

        self.guild_ = mock.Mock()

        self.music_bot_ = bot.MusicBot(
            self.guild_, self.dispatcher_.loop, self.dispatcher_.user
        )
        self.music_bot_.pafy_search = mock.Mock()
        self.music_bot_.youtube_search = mock.MagicMock()
        self.mock_audio_source_ = mock.Mock()
        self.music_bot_.create_audio_source = mock.Mock(
            return_value=self.mock_audio_source_
        )

    async def test_ignores_own_message(self):
        message = create_mock_message(
            contents="-Some bot message", author=self.dispatcher_.user
        )

        await self.music_bot_.handle_message(message)

        # Bot didn't respond with anything.
        message.channel.send.assert_not_awaited()

    async def test_ignores_message_without_command_prefix(self):
        ignore_message = create_mock_message(contents="Some non-command message")

        await self.music_bot_.handle_message(ignore_message)

        # Bot didn't respond with anything.
        ignore_message.channel.send.assert_not_awaited()

    async def test_hello_command_sends_message(self):
        hello_message = create_mock_message(contents="-hello")

        await self.music_bot_.handle_message(hello_message)

        hello_message.channel.send.assert_awaited_with(":wave: Hello! default_user")

    async def test_play_fails_when_user_not_in_voice_channel(self):
        play_message = create_mock_message(
            contents="-play song", author=create_mock_author()
        )

        await self.music_bot_.handle_message(play_message)

        play_message.channel.send.assert_awaited_with(
            ":studio_microphone: default_author, please join a voice channel to start "
            "the :robot:"
        )

    async def test_play_connects_deafaned(self):
        play_message = create_mock_message(
            contents="-play song",
            author=create_mock_author(
                voice_state=create_mock_voice_state(channel=create_mock_voice_channel())
            ),
        )

        mock_media = mock.Mock()
        mock_media.title.__repr__ = lambda self: "song"

        self.music_bot_.pafy_search = mock.Mock(return_value=mock_media)

        await self.music_bot_.handle_message(play_message)

        self.music_bot_.voice_client.guild.change_voice_state.assert_awaited_with(
            channel=play_message.author.voice.channel, self_deaf=True
        )

        self.assertEqual(
            self.music_bot_.voice_client.current_audio_source, self.mock_audio_source_
        )
        self.assertEqual(
            self.music_bot_.voice_client.after_callback, self.music_bot_.after_callback
        )

        play_message.channel.send.assert_called_once_with(
            ":notes: Now Playing :notes:\n```\nsong\n```"
        )

    async def test_second_play_command_queues_media(self):
        author = create_mock_author(
            voice_state=create_mock_voice_state(channel=create_mock_voice_channel())
        )
        play_message1 = create_mock_message(contents="-play song1", author=author)
        play_message2 = create_mock_message(contents="-play song2", author=author)

        mock_media = mock.Mock()
        self.music_bot_.pafy_search = mock.Mock(return_value=mock_media)
        mock_media.title.__repr__ = lambda _: "song1"

        await self.music_bot_.handle_message(play_message1)

        play_message1.channel.send.assert_called_once_with(
            ":notes: Now Playing :notes:\n```\nsong1\n```"
        )

        mock_media.title.__repr__ = lambda _: "song2"
        await self.music_bot_.handle_message(play_message2)

        play_message2.channel.send.assert_awaited_with(
            ":clipboard: Added to Queue\n```\nsong2\n```"
        )

        self.music_bot_.voice_client.finish_audio_source()

        await asyncio.sleep(0.1)

        play_message2.channel.send.assert_called_with(
            ":notes: Now Playing :notes:\n```\nsong2\n```"
        )

    async def test_play_livestream_informs_user_unable_to_play(self):
        mock_author = create_mock_author(
            voice_state=create_mock_voice_state(channel=create_mock_voice_channel())
        )
        play_message = create_mock_message(
            contents="-play livestream", author=mock_author
        )
        mock_media = mock.Mock()
        mock_media.title.__repr__ = lambda self: "livestream"
        mock_media.duration = "00:00:00"
        self.music_bot_.pafy_search = mock.Mock(return_value=mock_media)

        await self.music_bot_.handle_message(play_message)

        await asyncio.sleep(0.1)

        play_message.channel.send.assert_awaited_with(
            "Sorry, I can't play livestreams :sob:"
        )


if __name__ == "__main__":
    unittest.main()
