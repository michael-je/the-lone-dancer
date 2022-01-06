# The Lone Dancer - Discord music bot

This is a Discord bot centered around streaming music from **YouTube** into a voice channel. It is in active development and recieves regular feature updates and bug fixes.

---
## Main features
- Accepts links and search terms for audio streaming
- Play, pause, skip, queue, and more!
- Stream the audio into the voice channel you're in 🎶

---
## Quickstart
1. Install python dependencies (see Development setup below for troubleshooting):
		
		python3 -m pip install --no-deps -r requirements.txt

2. Set `DISCORD_TOKEN` in `.env` using `.env.example` as a base:

		cp .env.example .env
		$EDITOR .env

2a. For spotify album/playlist/track functionality add `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` from your [spotify app](https://developer.spotify.com/dashboard/)

3. Run the bot:
		
		python3 bot.py

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
5. Follow [this guide](https://discordpy.readthedocs.io/en/stable/discord.html) to create a bot and connect it to a Discord server.
6. Create a config file using the example:
		
		cp .env.example .env
	Then replace the empty `DISCORD_TOKEN` field with your generated token from the previous step.
7. Run the bot:

		python3 bot.py
8. Verify the bot is running by typing `-hello` in the Discord server with the bot.

---
## Usage

Once the bot is up and running you can control it by sending commands to any text channel in the Discord server. Commands look like: `-command`

You need to be connected to a voice channel to use any of the bot's voice streaming commands.

To get a list of available commands you can use the `-help` command.
