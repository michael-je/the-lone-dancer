## The Lone Dancer - Discord music bot
This project is still in development. The goal is to create a simple music playing bot for our discord server. It should be able to connect to a voice channel, accept basic commands and play back audio from youtube.

---
### Requirements
- python3
- python-pip

---
### Setup for contributions (Linux)
1. Fork the repository on github, clone it onto your machine and move into the directory:
	`$ git clone git@<your fork link>.git`
	`$ cd the-lone-dancer`
2. Optionally create a new virtual environment and activate it:
	`$ pip3 install virtualenv`
	`$ virtualenv venv`
	`$ source /venv/bin/activate`
3. Install required python libraries:
	`$ pip3 install -r requirements.txt`
4. Follow the beginning of [this guide](https://www.freecodecamp.org/news/create-a-discord-bot-with-python/) to create a discord bot and generate an API token for it. 
5. Create secrets.py using the example:
	`$ cp secrets.py.example secrets.py`
	Then replace the empty `TOKEN` string with your generated token from step 4.

---
### Useful links
- [setting up a basic discord bot](https://www.freecodecamp.org/news/create-a-discord-bot-with-python/)
- [discord.py](https://github.com/Rapptz/discord.py)
	- [documentation](https://discordpy.readthedocs.io/en/latest/quickstart.html#a-minimal-bot)
	- [example voice bot](https://github.com/Rapptz/discord.py/blob/master/examples/basic_voice.py) *Note that this example is thrown a 403 error when trying to connect to youtube*
- [The original discord music bot](https://github.com/k5van/Catharsis-Bot)

---
### Next Steps
- Figure out how to stream audio from youtube
	- [streaming audio from youtube - stackoverflow](https://stackoverflow.com/questions/49354232/how-to-stream-audio-from-a-youtube-url-in-python-without-download)
	- [streaming youtube LIVE into discord voice - stackoverflow](https://stackoverflow.com/questions/66610012/discord-py-streaming-youtube-live-into-voice)
	- [voice.create_ytdl_channel() - stackoverflow](https://stackoverflow.com/questions/57946894/discord-py-voiceclient-object-has-no-attribute-create-ytdl-player)
		- This method seems to require passing in a channel object. See info [here](https://stackoverflow.com/questions/52916317/get-the-name-of-a-channel-using-discord-py) about how to create these objects as well as getting ID's and such.
		Note that method names in this explanation seem to be slightly outdated (server has been changed to guild, fx) - see [here](https://discordpy.readthedocs.io/en/stable/migrating.html?highlight=client%20get_server)

---
### Logic
1. read from chat, accept:
	- search terms
	- youtube links
	- other basic commands (*play, pause, skip, etc*)
2. parse command (here we only discuss how to handle audio playback)
	- if the command is a search term rather than a youtube URL:
		- convert the search directly into a youtube search link using `urllib3.parse.quote_plus()`
		- parse the resulting page for the link to the first video
3. Stream the audio into the voice channel. *A few ideas:*
	1. visit the page using a browser and connect the output audio directly to the bot via some kind of audio sink/socket (jack?)
	2. use `voice.create_ytdl_channel()`, listed above.
	3. Use some other external tool like vlc or ffmpeg to capture the audio.
	4. *If audio cannot be streamed from youtube then we can try to download the video instead, and then play that back into the bot. This is probably easier than streaming, but not preferred.*
