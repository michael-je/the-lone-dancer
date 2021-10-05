import discord


class MusicBot(discord.Client):
    def __init__(self):
        super().__init__()

    decorator_helper = discord.Client()

    @decorator_helper.event
    async def on_ready(self):
        print(f"we have logged in as {self.user}")

    @decorator_helper.event
    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.startswith('!hello'):
            await message.channel.send('Hello!')

