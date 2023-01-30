import discord, game, asyncio, team, player #, league, obl, draft
# import main_controller
import database as db
import onomancer as ono
# from league_storage import league_exists, season_save, season_restart, get_mods, get_team_mods, set_mods
from flask import Flask
from client import client, config, setupmessages

# app = main_controller.app

watching = False
active_tournaments = []
active_leagues = []
active_standings = {}

# thread1 = threading.Thread(target=main_controller.update_loop)
# thread1.start()

@client.event
async def on_ready():
    global watching
    db.initialcheck()
    print(f"logged in as {client.user} with token {config['token']} to {len(client.guilds)} servers")
    commandtree = discord.app_commands.CommandTree(client)
    command_modules = [team, player, game]
    for cm in command_modules:
        for command in cm.COMMANDS:
            commandtree.add_command(command)
    await commandtree.sync()
    print(await commandtree.fetch_commands())
    if not watching:
        watching = True
        watch_task = asyncio.create_task(game.game_watcher())
        await watch_task


@client.event
async def on_reaction_add(reaction, user):
    if reaction.message in setupmessages.keys():
        game = setupmessages[reaction.message]
        try:
            if str(reaction.emoji) == "🔼" and not user == client.user:
                new_player = game.player(ono.get_stats(db.get_user_player(user)["name"]))
                game.teams["away"].add_lineup(new_player)
                await reaction.message.channel.send(f"{new_player} {new_player.star_string('batting_stars')} takes spot #{len(game.teams['away'].lineup)} on the away lineup.")
            elif str(reaction.emoji) == "🔽" and not user == client.user:
                new_player = game.player(ono.get_stats(db.get_user_player(user)["name"]))
                game.teams["home"].add_lineup(new_player)
                await reaction.message.channel.send(f"{new_player} {new_player.star_string('batting_stars')} takes spot #{len(game.teams['home'].lineup)} on the home lineup.")
        except:
            await reaction.message.channel.send(f"{user.display_name}, we can't find your idol. Maybe you don't have one yet?")

client.run(config["token"])
