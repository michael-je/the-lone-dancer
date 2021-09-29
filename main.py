import discord, asyncio

import secrets


class MusicBot(discord.Client):
    def __init__(self):
        super().__init__()

    # https://medium.com/@vadimpushtaev/decorator-inside-python-class-1e74d23107f6
    # https://stackoverflow.com/questions/7473096/python-decorators-how-to-use-parent-class-decorators-in-a-child-class
    super_instance = discord.Client()

    def event(self, coro):
        super().event(coro)

    @super_instance.event
    async def on_ready(self):
        print(f"We have logged in as {super().user}")

    @super_instance.event
    async def on_message(self, message):
        if message.author == helper.user:
            return
        if message.content.startswith('!hello'):
            await message.channel.send('Hello!')


musicBot = MusicBot()

# TODO figure out how to get environment variables to work
# musicBot.run(os.getenv('TOKEN'))
musicBot.run(secrets.TOKEN)
