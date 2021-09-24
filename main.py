import discord, os

import secrets

client = discord.Client()

# called when the bot is ready to be used
@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")

# called on message receive events
@client.event
async def on_message(message):
    # don't do anything if the message is from the bot
    if message.author == client.user:
        return
    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

# TODO figure out how to get environment variables to work
# client.run(os.getenv('TOKEN'))
client.run(secrets.TOKEN)
