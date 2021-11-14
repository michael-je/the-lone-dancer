import unittest
from unittest import mock
import bot
import asyncio


class MockVoiceClient:
    def __init__(self):
        self._after_callback = None
        self._current_audio_source = None
        self.guild = mock.AsyncMock()

    def is_playing(self):
        return self._current_audio_source is not None

    def play(self, audio_source, after = None):
        # Play should not be called something was already playing.
        assert(not self._current_audio_source)
        self._current_audio_source = audio_source
        self._after_callback = after

    def stop(self):
        self._current_audio_source = None
        self._after_callback(None)
        self._after_callback = None

    def _finish_audio_source(self, exception = None):
        self._after_callback(exception)
        self._current_audio_source = None

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

    def author_eq(self, x):
        return self.author_str == x

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
    def setUp(self):
        self.dispatcher_ = mock.Mock()
        self.dispatcher_.user = create_mock_author(name="test_bot")

        self.guild_ = mock.Mock()
        self.music_bot_ = bot.MusicBot(self.guild_, self.dispatcher_)
        self.music_bot_.pafy_search = mock.Mock()
        self.music_bot_.youtube_search = mock.MagicMock()
        self.mock_audio_source_ = mock.Mock()
        self.music_bot_.create_audio_source = mock.Mock(
            return_value=self.mock_audio_source_
        )

    async def asyncSetUp(self):
        self.dispatcher_.loop = asyncio.get_running_loop()

    async def test_ignores_own_message(self):
        play_message = create_mock_message(
            contents="!Some bot message", author=self.dispatcher_.user
        )

        await self.music_bot_.handle_message(play_message)

        # Bot didn't respond with anything.
        play_message.channel.send.assert_not_awaited()

    async def test_ignores_message_without_command_prefix(self):
        ignore_message = create_mock_message(contents="Some non-command message")

        await self.music_bot_.handle_message(ignore_message)

        # Bot didn't respond with anything.
        ignore_message.channel.send.assert_not_awaited()

    async def test_hello_command_sends_message(self):
        hello_message = create_mock_message(contents="!hello")

        await self.music_bot_.handle_message(hello_message)

        hello_message.channel.send.assert_awaited_with(":wave: Hello! default_user")

    async def test_play_complains_when_user_not_in_voice_channel(self):
        play_message = create_mock_message(
            contents="!play song", author=create_mock_author()
        )

        await self.music_bot_.handle_message(play_message)

        play_message.channel.send.assert_awaited_with(
            ":studio_microphone: default_author, please join a voice channel to start the :robot:"
        )

    async def test_play_connects_deafaned(self):
        play_message = create_mock_message(
            contents="!play song",
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

        self.assertEqual(self.music_bot_.voice_client._current_audio_source, self.mock_audio_source_)
        self.assertEqual(self.music_bot_.voice_client._after_callback, self.music_bot_.after_callback)

        play_message.channel.send.assert_called_once_with(
            f":notes: Now Playing :notes:\n```\nsong\n```"
        )

    async def test_two_play_commands_queues_media(self):
        author = create_mock_author(
                voice_state=create_mock_voice_state(channel=create_mock_voice_channel())
                )
        play_message1 = create_mock_message(
            contents="!play song1",
            author=author
        )
        play_message2 = create_mock_message(
            contents="!play song2",
            author=author
            )

        mock_media = mock.Mock()
        self.music_bot_.pafy_search = mock.Mock(return_value=mock_media)
        mock_media.title.__repr__ = lambda self: "song1"

        await self.music_bot_.handle_message(play_message1)

        play_message1.channel.send.assert_called_once_with(
            ":notes: Now Playing :notes:\n```\nsong1\n```"
        )

        mock_media.title.__repr__ = lambda self: "song2"
        await self.music_bot_.handle_message(play_message2)

        play_message2.channel.send.assert_awaited_with(
                ":clipboard: Added to Queue\n```\nsong2\n```"
                )

        self.music_bot_.voice_client._finish_audio_source()

        play_message2.channel.send.assert_called_with(
                ":notes: Now Playing :notes:\n```\nsong2\n```"
                )


if __name__ == "__main__":
    unittest.main()
