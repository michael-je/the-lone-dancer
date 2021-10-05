import bot, secrets


if __name__ == '__main__':
    musicBot = bot.MusicBot()

    # TODO figure out how to get environment variables to work and use instead of secrets.py
    # musicBot.run(os.getenv('TOKEN'))
    musicBot.run(secrets.TOKEN)

