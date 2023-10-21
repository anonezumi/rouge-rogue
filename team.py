import random, discord, jsonpickle, asyncio, math, player
import database as db
import onomancer as ono
from config import client, config
from league_storage import get_team_mods

class Team(object):
    def __init__(self):
        self.name = None
        self.lineup = []
        self.rotation = []
        self.slogan = None

    def find_player(self, name):
        for index in range(0,len(self.lineup)):
            if self.lineup[index].name.replace(" ", " ") == name:
                return (self.lineup[index], index, self.lineup)
        for index in range(0,len(self.rotation)):
            if self.rotation[index].name.replace(" ", " ") == name:
                return (self.rotation[index], index, self.rotation)
        else:
            return (None, None, None)

    def find_player_spec(self, name, roster):
         for s_index in range(0,len(roster)):
            if roster[s_index].name.replace(" ", " ") == name:
                return (roster[s_index], s_index)

    def average_stars(self):
        total_stars = 0
        for _player in self.lineup:
            total_stars += _player.stats["batting_stars"]
        for _player in self.rotation:
            total_stars += _player.stats["pitching_stars"]
        return total_stars/(len(self.lineup) + len(self.rotation))

    def swap_player(self, name):
        this_player, index, roster = self.find_player(name)
        if this_player is not None and len(roster) > 1:
            if roster == self.lineup:
                if self.add_pitcher(this_player):
                    roster.pop(index)
                    return True
            else:
                if self.add_lineup(this_player)[0]:
                    self.rotation.pop(index)
                    return True
        return False

    def delete_player(self, name):
        this_player, index, roster = self.find_player(name)
        if this_player is not None and len(roster) > 1:
            roster.pop(index)
            return True
        else:
            return False

    def slide_player(self, name, new_spot):
        this_player, index, roster = self.find_player(name)
        if this_player is not None and new_spot <= len(roster):
            roster.pop(index)
            roster.insert(new_spot-1, this_player)
            return True
        else:
            return False

    def slide_player_spec(self, this_player_name, new_spot, roster):
        index = None
        for s_index in range(0,len(roster)):
            if roster[s_index].name == this_player_name:
                index = s_index
                this_player = roster[s_index]
        if index is None:
            return False
        elif new_spot <= len(roster):
            roster.pop(index)
            roster.insert(new_spot-1, this_player)
            return True
        else:
            return False
                
    def add_lineup(self, new_player):
        if len(self.lineup) < 20:
            self.lineup.append(new_player)
            return (True,)
        else:
            return (False, "20 players in the lineup, maximum. We're being really generous here.")
    
    def add_pitcher(self, new_player):
        if len(self.rotation) < 8:
            self.rotation.append(new_player)
            return True
        else:
            return False

    def set_pitcher(self, rotation_slot = None, use_lineup = False):
        temp_rotation = self.rotation.copy()
        if use_lineup:         
            for batter in self.lineup:
                temp_rotation.append(batter)
        if rotation_slot is None:
            self.pitcher = random.choice(temp_rotation)
        else:
            self.pitcher = temp_rotation[(rotation_slot-1) % len(temp_rotation)]

    def apply_team_mods(self, league_name):
        mod_dic = get_team_mods(league_name, self.name)
        if mod_dic != {} and mod_dic != None:
            for player_name in iter(mod_dic.keys()):
                this_player = self.find_player(player_name)[0]
                if this_player is not None:
                    this_player.apply_mods(mod_dic[player_name])

    def finalize(self):
        if self.is_ready():
            if self.pitcher == None:
                self.set_pitcher()
            while len(self.lineup) <= 4:
                self.lineup.append(random.choice(self.lineup))       
            return self
        else:
            return False

@discord.app_commands.command()
async def showteam(inter: discord.Interaction, team_name: str):
    team = get_team_fuzzy_search(team_name)
    if team is not None:
        await inter.response.send_message(embed=build_team_embed(team))
    else:
        await inter.response.send_message(content="Can't find that team, boss. Typo?")

@discord.app_commands.command()
async def showallteams(inter: discord.Interaction):
    list_task = asyncio.create_task(team_pages(inter, get_all_teams()))
    await list_task

@discord.app_commands.command()
async def deleteteam(inter: discord.Interaction, team_name: str):
    team, owner_id = get_team_and_owner(team_name)
    if owner_id != inter.user.id and inter.user.id not in config["owners"]: #returns if person is not owner and not bot mod
        await inter.response.send_message(content="That team ain't yours, chief. If you think that's not right, bug xvi about deleting it for you.")
    else:
        delete_task = asyncio.create_task(team_delete_confirm(inter, team))
        await delete_task

@discord.app_commands.command()
async def assignowner(inter: discord.Interaction, owner: discord.User, team: str):
    if inter.user.id in config["owners"]:
        if db.assign_owner(team, owner.id):
            await inter.response.send_message(f"{team} is now owned by {owner.display_name}. Don't break it.")
        else:
            await inter.response.send_message("We couldn't find that team. Typo?")

@discord.app_commands.command()
async def saveteam(inter: discord.Interaction, name: str, slogan: str, batters: str, pitchers: str):
    if db.get_team(name) == None:
        # await inter.followup.send("Fetching players...")
        team = await create_team(inter, name, slogan, batters.split(","), pitchers.split(","))
        save_task = asyncio.create_task(save_team_confirm(inter, team))
        await save_task
    else:
        await inter.response.send_message(f"{name} already exists. Try a new name, maybe?")

@discord.app_commands.command()
async def searchteams(inter: discord.Interaction, search_term: str):
    if len(search_term) > 30:
        await inter.response.send_message("Team names can't even be that long, chief. Try something shorter.")
    else:
        list_task = asyncio.create_task(team_pages(inter, search_team(search_term), search_term=search_term))
        await list_task

@discord.app_commands.command()
async def swapsection(inter: discord.Interaction, team_name: str, player_name: str):
    team, owner_id = get_team_and_owner(team_name)
    if team is None:
        await inter.response.send_message("Can't find that team, boss. Typo?")
    elif owner_id != inter.user.id and inter.user.id not in config["owners"]:
        await inter.response.send_message("You're not authorized to mess with this team. Sorry, boss.")
    elif not team.swap_player(player_name):
        await inter.response.send_message("Either we can't find that player, you've got no space on the other side, or they're your last member of that side of the roster. Can't field an empty lineup, and we *do* have rules, chief.")
    else:
        await inter.response.send_message(f"Alright, {player_name} has been moved.", embed=build_team_embed(team))
        update_team(team)

@discord.app_commands.command()
async def moveplayer(inter: discord.Interaction, team_name: str, player_name: str, position: int):
    team, owner_id = get_team_and_owner(team_name)
    if team is None:
        await inter.response.send_message("Can't find that team, boss. Typo?")
    elif owner_id != inter.user.id and inter.user.id not in config["owners"]:
        await inter.response.send_message("You're not authorized to mess with this team. Sorry, boss.")
    else:
        player = team.find_player(player_name)
        if player[2] is None or len(player[2]) < position:
            await inter.response.send_message("You either gave us a number that was bigger than your current roster, or we couldn't find the player on the team. Try again.")
            return

        if team.slide_player_spec(player_name, position, player[2]):
            await inter.response.send_message("Done and done.", embed=build_team_embed(team))
            update_team(team)
        else:
            await inter.response.send_message("You either gave us a number that was bigger than your current roster, or we couldn't find the player on the team. Try again.")

@discord.app_commands.command()
async def addplayer(inter: discord.Interaction, player_name: str, team_name: str, is_pitcher: bool):
    if len(player_name) > 70:
        await inter.response.send_message("70 characters per player, boss. Quit being sneaky.")
        return
    team, owner_id = get_team_and_owner(team_name)
    if team is None:
        await inter.response.send_message("Can't find that team, boss. Typo?")
    elif owner_id != inter.user.id and inter.user.id not in config["owners"]:
        await inter.response.send_message("You're not authorized to mess with this team. Sorry, boss.")

    new_player = player.Player(ono.get_stats(player_name))

    if not is_pitcher:
        if not team.add_lineup(new_player):
            await inter.response.send_message("Too many batters 🎶")
            return
    else:
        if not team.add_pitcher(new_player):
            await inter.response.send_message("8 pitchers is quite enough, we think.")
            return

    await inter.response.send_message("Player added.", embed=build_team_embed(team))
    update_team(team)

@discord.app_commands.command()
async def removeplayer(inter: discord.Interaction, player_name: str, team_name: str):
    team, owner_id = get_team_and_owner(team_name)
    if team is None:
        await inter.response.send_message("Can't find that team, boss. Typo?")
    elif owner_id != inter.user.id and inter.user.id not in config["owners"]:
        await inter.response.send_message("You're not authorized to mess with this team. Sorry, boss.")
    elif not team.delete_player(player_name):
        await inter.response.send_message("We've got bad news: that player isn't on your team. The good news is that... that player isn't on your team?")
    else:
        await inter.response.send_message("Player removed.", embed=build_team_embed(team))
        update_team(team)

def get_team_fuzzy_search(team_name):
    team = get_team(team_name)
    if team is None:
        teams = search_team(team_name.lower())
        if len(teams) == 1:
            team = teams[0]
    return team

def get_team(name):
    try:
        team_json = jsonpickle.decode(db.get_team(name)[0], keys=True, classes=Team)
        if team_json is not None:
            if team_json.pitcher is not None: #detects old-format teams, adds pitcher
                team_json.rotation.append(team_json.pitcher)
                team_json.pitcher = None
                update_team(team_json)
            for player in team_json.rotation + team_json.lineup:
                if player.name == "Tim Locastro":
                    player.randomize_stars()
            return team_json
        return None
    except AttributeError:
        team_json.rotation = []
        team_json.rotation.append(team_json.pitcher)
        team_json.pitcher = None
        update_team(team_json)
        return team_json
    except:
        return None

def search_team(search_term):
    teams = []
    for team_pickle in db.search_teams(search_term):
        team_json = jsonpickle.decode(team_pickle[0], keys=True, classes=Team)
        try:         
            if team_json.pitcher is not None:
                if len(team_json.rotation) == 0: #detects old-format teams, adds pitcher
                    team_json.rotation.append(team_json.pitcher)
                    team_json.pitcher = None
                    update_team(team_json)
            for player in team_json.rotation + team_json.lineup:
                if player.name == "Tim Locastro":
                    player.randomize_stars()
        except AttributeError:
            team_json.rotation = []
            team_json.rotation.append(team_json.pitcher)
            team_json.pitcher = None
            update_team(team_json)
        except:
            return None

        teams.append(team_json)
    return teams

def get_team_and_owner(name):
    try:
        counter, name, team_json_string, timestamp, owner_id = db.get_team(name, owner=True)
        team_json = jsonpickle.decode(team_json_string, keys=True, classes=Team)
        if team_json is not None:
            if team_json.pitcher is not None: #detects old-format teams, adds pitcher
                team_json.rotation.append(team_json.pitcher)
                team_json.pitcher = None
                update_team(team_json)
            for player in team_json.rotation + team_json.lineup:
                if player.name == "Tim Locastro":
                    player.randomize_stars()
            return (team_json, owner_id)
        return (None, None)
    except AttributeError:
        team_json.rotation = []
        team_json.rotation.append(team_json.pitcher)
        team_json.pitcher = None
        update_team(team_json)
        return (team_json, owner_id)
    except:
        return None

def save_team(this_team, user_id):
    try:
        this_team.prepare_for_save()
        team_json_string = jsonpickle.encode(this_team, keys=True)
        db.save_team(this_team.name, team_json_string, user_id)
        return True
    except:
        return None

def update_team(this_team):
    try:
        this_team.prepare_for_save()
        team_json_string = jsonpickle.encode(this_team, keys=True)
        db.update_team(this_team.name, team_json_string)
        return True
    except:
        return None

def get_all_teams():
    teams = []
    for team_pickle in db.get_all_teams():
        this_team = jsonpickle.decode(team_pickle[0], keys=True, classes=Team)
        teams.append(this_team)
    return teams

def get_filtered_teams(teams_to_remove):
    teams = []
    for team_pickle in db.get_all_teams():
        this_team = jsonpickle.decode(team_pickle[0], keys=True, classes=Team)
        if this_team.name not in teams_to_remove:
            teams.append(this_team)
    return teams

def build_team_embed(team):
    embed = discord.Embed(color=discord.Color.purple(), title=team.name)
    lineup_string = ""
    for player in team.lineup:
        lineup_string += f"{player.name} {player.star_string('batting_stars')}\n"

    rotation_string = ""
    for player in team.rotation:
        rotation_string += f"{player.name} {player.star_string('pitching_stars')}\n"
    embed.add_field(name="Rotation:", value=rotation_string, inline = False)
    embed.add_field(name="Lineup:", value=lineup_string, inline = False)
    embed.add_field(name="█a██:", value=str(abs(hash(team.name)) % (10 ** 4)))
    embed.set_footer(text=team.slogan)
    return embed

async def team_pages(inter, all_teams, search_term=None):
    pages = []
    page_max = math.ceil(len(all_teams)/25)
    if search_term is not None:
        title_text = f"All teams matching \"{search_term}\":"
    else:
        title_text = "All Teams"

    for page in range(0,page_max):
        embed = discord.Embed(color=discord.Color.purple(), title=title_text)
        embed.set_footer(text = f"Page {page+1} of {page_max}")
        for i in range(0,25):
            try:
                if all_teams[i+25*page].slogan.strip() != "":
                    embed.add_field(name=all_teams[i+25*page].name, value=all_teams[i+25*page].slogan)
                else:
                    embed.add_field(name=all_teams[i+25*page].name, value="404: Slogan not found")
            except:
                break
        pages.append(embed)
    await inter.response.send_message(embed=pages[0])
    teams_list = await inter.original_response()
    current_page = 0
    if page_max > 1:
        await teams_list.add_reaction("◀")
        await teams_list.add_reaction("▶")

        def react_check(react, user):
            return user == inter.user and react.message == teams_list

        while True:
            try:
                react, user = await client.wait_for('reaction_add', timeout=60.0, check=react_check)
                if react.emoji == "◀" and current_page > 0:
                    current_page -= 1
                    await react.remove(user)
                elif react.emoji == "▶" and current_page < (page_max-1):
                    current_page += 1
                    await react.remove(user)
                await teams_list.edit(embed=pages[current_page])
            except asyncio.TimeoutError:
                return

async def create_team(inter, name, slogan, batters, pitchers):
    newteam = Team()
    newteam.name = name
    newteam.slogan = slogan

    if len(newteam.name) > 30:
        await inter.response.send_message("Team names have to be less than 30 characters! Try again.")
    elif len(newteam.slogan) > 100:
        await inter.response.send_message("We've given you 100 characters for the slogan. Discord puts limits on us and thus, we put limits on you. C'est la vie.")

    for batter in batters:
        if len(batter) > 70:
            await inter.response.send_message(f"{batter} is too long, chief. 70 or less.")
            return
        stats = ono.get_stats(batter.rstrip())
        if stats is None:
            await inter.response.send_message("Onomancer bungled it.")
        newteam.add_lineup(player.Player(stats))

    for pitcher in pitchers:
        if len(pitcher) > 70:
            await inter.response.send_message(f"{pitcher} is too long, chief. 70 or less.")
            return
        stats = ono.get_stats(pitcher.rstrip())
        if stats is None:
            await inter.response.send_message("Onomancer bungled it.")
        newteam.add_pitcher(player.Player(stats))

    return newteam

async def save_team_confirm(inter: discord.Interaction, newteam):
    await inter.response.send_message("Here's your team. Looks good?", embed=build_team_embed(newteam))
    checkmsg = await inter.original_response()
    await checkmsg.add_reaction("👍")
    await checkmsg.add_reaction("👎")

    def react_check(react, user):
        return user == inter.user and react.message == checkmsg

    try:
        react, user = await client.wait_for('reaction_add', timeout=30.0, check=react_check)
        if react.emoji == "👍":
            save_team(newteam, inter.user.id)
            await inter.channel.send("Saved! Thank you for flying Air Matteo. We hope you had a pleasant data entry.")
            return
        elif react.emoji == "👎":
            await inter.channel.send("Message received. Pumping brakes, turning this car around. Try again, chief.")
            return
    except asyncio.TimeoutError:
        await inter.channel.send("Look, we don't have all day. 30 seconds is long enough, right? Try again.")
        return

async def team_delete_confirm(inter: discord.Interaction, team):
    await inter.response.send_message(content="Do you want to delete this team?", embed=build_team_embed(team))
    checkmsg = inter.original_response()
    await checkmsg.add_reaction("👍")
    await checkmsg.add_reaction("👎")

    def react_check(react, user):
        return user == inter.user and react.message == checkmsg

    try:
        react, user = await client.wait_for('reaction_add', timeout=20.0, check=react_check)
        if react.emoji == "👍":
            if db.delete_team(team):
                await inter.response.send_message("Job's done. We'll clean up on our way out, don't worry.")
            else:
                await inter.response.send_message("Huh. Didn't quite work. Tell xvi next time you see xer.")
            return
        elif react.emoji == "👎":
            await inter.response.send_message("Message received. Pumping brakes, turning this car around.")
            return
    except asyncio.TimeoutError:
        await inter.response.send_message("Guessing you got cold feet, so we're putting the axe away. Let us know if we need to fetch it again, aye?")
        return

COMMANDS = [showteam, showallteams, deleteteam, assignowner, saveteam, searchteams, swapsection, moveplayer, addplayer, removeplayer]