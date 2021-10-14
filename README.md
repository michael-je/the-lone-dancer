# The Lone Dancer - Discord music bot
This project is still in development. The goal is to create a simple music playing bot for our discord server. It should be able to connect to a voice channel, accept basic commands and play back audio from youtube.

---
## Quickstart
1. Install python dependencies (see Development setup below for troubleshooting):
		
		python3 -m pip install --no-deps -r requirements.txt

2. Set `DISCORD_TOKEN` in `.env` using `.env.example` as a base:

		cp .env.example .env
		$EDITOR .env

3. Run the bot:
		
		python3 bot.py

---
## Main features
- Accepts links and search terms for audio streaming
- Play, pause, skip, scrub, queue, and more!
- Stream the audio into the voice channel you're in 🎶

---
## Docker build
Simply build and run the container:

		docker build . -t the-lone-dancer:latest
		docker run --env-file .env the-lone-dancer

---
## Development setup (Linux)
### Requirements
- `python >= 3.7`
- `discord.py`
- `ffmpeg`

### Setup
1. Make sure `python3` and `python-pip` are installed. (On Arch-Linux):
		
		sudo pacman -Syu
		sudo pacman -S python3 python-pip
2. Fork the repository on github, clone it onto your machine and move into the directory:
	
		git clone git@<your-fork>.git
		cd the-lone-dancer
3. Optionally create a new virtual environment and activate it:

		pip3 install virtualenv
		virtualenv venv
		source venv/bin/activate
4. Install required python libraries:

		pip3 install -r requirements.txt
5. Follow the beginning of [this guide](https://www.freecodecamp.org/news/create-a-discord-bot-with-python#how-to-create-a-discord-bot-account) to create a discord bot and generate an API token for it. 
6. Create a config file using the example:
		
		cp .env.example .env
	Then replace the empty `DISCORD_TOKEN` field with your generated token from the previous step.
7. [Connect the bot to a discord server](https://www.freecodecamp.org/news/create-a-discord-bot-with-python/#how-to-invite-your-bot-to-join-a-server) for testing; make sure to give it relevant permissions.
8. Run the bot:

		python3 bot.py
9. Verify the bot is running by typing `!hello` in the discord server with the bot.

---
### Next Steps
- Figure out how to stream audio from youtube
	- [streaming audio from youtube - stackoverflow](https://stackoverflow.com/questions/49354232/how-to-stream-audio-from-a-youtube-url-in-python-without-download)
	- [streaming youtube LIVE into discord voice - stackoverflow](https://stackoverflow.com/questions/66610012/discord-py-streaming-youtube-live-into-voice)
	- [voice.create_ytdl_channel() - stackoverflow](https://stackoverflow.com/questions/57946894/discord-py-voiceclient-object-has-no-attribute-create-ytdl-player)
		- This method seems to require passing in a channel object. See info [here](https://stackoverflow.com/questions/52916317/get-the-name-of-a-channel-using-discord-py) about how to create these objects as well as getting ID's and such.
		Note that method names in this explanation seem to be slightly outdated (server has been changed to guild, fx) - see [here](https://discordpy.readthedocs.io/en/stable/migrating.html?highlight=client%20get_server)

---
### Useful links
- [setting up a basic discord bot](https://www.freecodecamp.org/news/create-a-discord-bot-with-python/)
- [discord.py](https://github.com/Rapptz/discord.py)
	- [documentation](https://discordpy.readthedocs.io/en/latest/quickstart.html#a-minimal-bot)
	- [example voice bot](https://github.com/Rapptz/discord.py/blob/master/examples/basic_voice.py) *Note that this example throws a 403 error when trying to connect to youtube*
- [The original discord music bot](https://github.com/k5van/Catharsis-Bot)
