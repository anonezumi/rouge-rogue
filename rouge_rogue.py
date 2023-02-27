import discord, asyncio, team, player, game
import database as db
from client import client, config

initialized = False

@client.event
async def on_ready():
    global initialized
    db.initialcheck()
    print(f"logged in as {client.user} to {len(client.guilds)} servers")
    commandtree = discord.app_commands.CommandTree(client)
    command_modules = [team, player, game]
    for cm in command_modules:
        for command in cm.COMMANDS:
            commandtree.add_command(command)
    await commandtree.sync()
    if not initialized:
        initialized = True
        watch_task = asyncio.create_task(game.update_loop())
        await watch_task

client.run(config["token"])
