import discord, json
import onomancer as ono
import database as db

class Player(object):
    def __init__(self, json_string):
        self.stlats = json.loads(json_string)
        self.id = self.stlats["id"]
        self.name = self.stlats["name"]
        self.game_stats = {
                            "outs_pitched" : 0,
                            "walks_allowed" : 0,
                            "hits_allowed" : 0,
                            "strikeouts_given" : 0,
                            "runs_allowed" : 0,
                            "plate_appearances" : 0,
                            "walks_taken" : 0,
                            "sacrifices" : 0,
                            "hits" : 0,
                            "home_runs" : 0,
                            "total_bases" : 0,
                            "rbis" : 0,
                            "strikeouts_taken" : 0
            }
        
    def star_string(self, key):
        str_out = ""
        starstring = str(self.stlats[key])
        if ".5" in starstring:
            starnum = int(starstring[0])
            addhalf = True
        else:
            starnum = int(starstring[0])
            addhalf = False
        str_out += "⭐" * starnum
        if addhalf:
            str_out += "✨"
        return str_out

    def __str__(self):
        return self.name

    def apply_mods(self, mod_dic):
        for stat in iter(mod_dic.keys()):
            self.stlats[stat] = self.stlats[stat] + mod_dic[stat]

@discord.app_commands.command()
async def showplayer(inter: discord.Interaction, player_name: str):
    player_stats = json.loads(ono.get_stats(player_name))
    await inter.response.send_message(embed=build_star_embed(player_stats))

@discord.app_commands.command()
async def idolize(inter: discord.Interaction, player_name: str):
    player_stats = json.loads(ono.get_stats(player_name))
    db.designate_player(inter.user, player_stats)
    await inter.response.send_message(content="{} is now your idol!".format(player_name), embed=build_star_embed(player_stats))

@discord.app_commands.command()
async def showidol(inter: discord.Interaction, user: discord.User = None):
    if user is None: user = inter.user
    try:
        player_json = db.get_user_player(user)
        await inter.response.send_message(content="{}'s idol is {}.".format(user.display_name, player_json["name"]), embed=build_star_embed(player_json))
    except:
        await inter.response.send_message(content="We can't find your idol. Looked everywhere, too.")

def build_star_embed(player_json):
    starkeys = {"batting_stars" : "Batting", "pitching_stars" : "Pitching", "baserunning_stars" : "Baserunning", "defense_stars" : "Defense"}
    embed = discord.Embed(color=discord.Color.purple(), title=player_json["name"])

    for key in starkeys.keys():
        embedstring = ""
        starstring = str(player_json[key])
        starnum = int(starstring[0])
        addhalf = ".5" in starstring
        embedstring += "⭐" * starnum
        if addhalf:
            embedstring += "✨"
        elif starnum == 0:  # why check addhalf twice, amirite
            embedstring += "⚪️"
        embed.add_field(name=starkeys[key], value=embedstring, inline=False)
    return embed

COMMANDS = [showplayer, idolize, showidol]