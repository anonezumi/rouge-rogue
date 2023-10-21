import random, weather, team, player, discord, asyncio, voice, stats, yaml
from config import config

gamesarray = []

class Pitch():
    def __init__(self):
        self.in_strike_zone = False
        self.swing = False
        self.hit = False
        self.speed = 0
        self.x = 0
        self.z = 0

class Hit():
    def __init__(self):
        self.hori_angle = 45
        self.vert_angle = 0
        self.distance = 0
        self.hit_type = "none"

class PlateAppearance():
    def __init__(self):
        self.batter = None
        self.pitcher = None
        self.defender = None
        self.offense_team = None
        self.defense_team = None
        self.strikes = 0
        self.balls = 0
        self.outs = 0
        self.runs = 0
        self.displaytext = ""
        self.runners = [None] * 4 # list of tuples (runner: Player, bases run: int). should always be a list of length bases+1
        self.pitches = []
        self.hit = None

class StealAttempt():
    def __init__(self):
        self.thief = None
        self.defender = None
        self.success = None

class Game(object):
    def __init__(self, teams, inter, length=None, voice=None, weather_name="Sunny"):
        self.inning = 1
        self.outs = 0
        self.over = False
        self.victory_lap = False
        self.current_pa = None
        self.baserunners = [None] * 3
        self.message_queue = []
        self.inning_part = 0

        self.teams = [GameTeam(t) for t in teams]
        self.offense_team = self.teams[0]
        self.defense_team = self.teams[1]
        self.current_batter = self.offense_team.lineup[self.offense_team.lineup_position]
        self.current_pitcher = self.defense_team.pitcher
        self.inter = inter
        if length is not None:
            self.max_innings = length
        else:
            self.max_innings = config["default_length"]
        self.voice = voice
        self.weather = weather.all_weathers()[weather_name](self)

    def plate_appearance(self):
        self.current_pa = PlateAppearance()
        pa = self.current_pa
        pa.batter = self.current_batter
        self.attempt_steals()
        if self.outs >= 3:
            self.flip_inning()
            return
        while True:
            pitch = self.pitch()
            pa.pitches.append(pitch)
            if pitch.hit:
                self.hit(pitch)
            elif pitch.swing or pitch.in_strike_zone:
                pa.strikes += 1
                if pa.strikes >= 3:
                    self.batter_out()
                    break
            else:
                pa.balls += 1
                if pa.balls >= 4:
                    self.walk()
                    break
        
        self.message_queue.append("S: {.strikes} B: {.balls} O: {.outs} R: {.runs}".format(self.current_pa))

        self.outs += pa.outs
        if self.outs >= 3:
            self.flip_inning()
    
    def batter_out(self):
        self.current_pa.outs += 1
        self.current_batter = self.offense_team.get_next_batter()
    
    def walk(self):
        self.current_pa.runners[0] = (self.current_batter, 1)
        i = 0
        for br in self.baserunners:
            i += 1
            if br:
                self.current_pa.runners[i] = (br, 1)
            else: break
    
    def attempt_steals(self):
        for i in range(len(self.baserunners) - 1): # -1 so nobody steals home (maybe they can in stella mode?)
            if not self.baserunners[i]: continue # can't steal if you don't exist (sad)
            if self.baserunners[i+1]: continue # can't steal an occupied base
            attempt = stats.roll_chance() # whether they try to steal
            if attempt:
                success = stats.roll_chance() # whether they succeed in stealing
                if success:
                    self.baserunners[i+1] = self.baserunners[i]
                else:
                    self.outs += 1
                self.baserunners[i] = None

    def pitch(self):
        pitch = Pitch()
        pitch.speed = 60 + (40 * stats.roll()) # range 60 to 100
        pitch.x = stats.roll() # higher number means closer to center of strike zone
        pitch.z = stats.roll() # ditto
        pitch.in_strike_zone = (pitch.x > 0.25 and pitch.z > 0.25) # about a 56% chance
        pitch.swing = stats.roll_chance()
        pitch.hit = pitch.in_strike_zone and pitch.swing and stats.roll_chance(threshold=0.7)
        return pitch

    def hit(self, pitch):
        hit = Hit()
        self.current_pa.hit = hit
        foul = stats.roll_chance(threshold=0.4)
        if foul:
            hit.hit_type = "foul"
            if self.current_pa.strikes < 2:
                self.current_pa.strikes += 1
            return
        vert = stats.roll()
        if vert <= 0.4:
            hit.hit_type = "groundball"
        elif vert <= 0.65:
            hit.hit_type = "line drive"
        elif vert <= 0.97:
            hit.hit_type = "flyball"
        else:
            hit.hit_type = "infield fly"
            self.batter_out()

    def flip_inning(self):
        if self.inning_part == len(self.teams) + 1:
            self.inning += 1
            self.inning_part = 0
            self.offense_team = self.teams[0]
            self.defense_team = self.teams[1]
        else:
            self.inning_part += 1
            self.offense_team = self.teams[self.inning_part]
            self.defense_team = self.teams[(self.inning_part + 1) % len(self.teams)]
 
class GameTeam(): # a specific instance of a team for participating in a game
    def __init__(self, team: team.Team):
        self.team = team
        self.name = team.name
        self.lineup = [GamePlayer(p) for p in team.lineup]
        self.lineup_position = 0
        self.pitcher = GamePlayer(random.choice(team.rotation))
        self.score = 0
    
    def get_next_batter(self):
        if self.lineup_position == len(self.lineup) + 1:
            self.lineup_position = 0
        else:
            self.lineup_position += 1
        return self.lineup[self.lineup_position]

class GamePlayer(): # a specific instance of a player for participating in a game
    def __init__(self, player: player.Player):
        self.player = player
        self.id = player.id
        self.name = player.name

@discord.app_commands.command()
async def startgame(inter: discord.Interaction, home: str, away: str, weather_name: str = "Sunny", voice: str = None, innings: int = 9):
    if config["game_freeze"]:
        await inter.response.send_message("Patch incoming. We're not allowing new games right now.")
        return
    
    if weather_name is not None and weather_name not in weather.all_weathers():
        await inter.response.send_message("Can't find that weather.")
        return

    if voice is not None and voice not in [v["name"] for v in voice.all_voices]:
        await inter.response.send_message("Can't find that broadcaster.")
        return
    
    home_team = team.get_team_fuzzy_search(home)
    if home_team is None:
        await inter.response.send_message("Can't find that home team.")
        return

    away_team = team.get_team_fuzzy_search(away)
    if away_team is None:
        await inter.response.send_message("Can't find that away team.")
        return

    if innings < 2 and inter.user.id not in config["owners"]:
        await inter.response.send_message(content="Anything less than 2 innings isn't even an outing. Try again.")
        return

    if innings > 200 and inter.user.id not in config["owners"]:
        await inter.response.send_message(content="Current inning limit is 200. That should be plenty, really.")
        return

    game = Game([home_team, away_team], inter, length=innings, voice=voice)

    game_task = asyncio.create_task(prepare_game(game))
    await game_task

@discord.app_commands.command()
async def startrandomgame(inter: discord.Interaction):
    if config["game_freeze"]:
        await inter.response.send_message(content="Patch incoming. We're not allowing new games right now.")
        return

    teamslist = team.get_all_teams()

    game = Game(random.choice(teamslist).finalize(), random.choice(teamslist).finalize(), inter)

    game_task = asyncio.create_task(prepare_game(game))
    await game_task

async def prepare_game(newgame):
    #if newgame.weather.name == "Sunny":
    #    weathers = weather.all_weathers()
    #    newgame.weather = weathers[random.choice(list(weathers.keys()))](newgame)

    if newgame.voice is None:
        newgame.voice = random.choice(voice.all_voices)

    await newgame.inter.response.send_message(f"{newgame.teams[1].name} vs. {newgame.teams[0].name}, starting now!")
    gamesarray.append(newgame)

def game_over_embed(game):
    title_string = f"{game.teams[1].name} at {game.teams[0].name} ended after {game.inning-1} innings"
    if (game.inning - 1) > game.max_innings: #if extra innings
        title_string += f" with {game.inning - (game.max_innings+1)} extra innings.\n"
    else:
        title_string += ".\n"

    winning_team = game.teams[0].name if game.teams[0].score > game.teams[1].score else game.teams[1].name
    winstring = f"{game.teams[1].score} to {game.teams[0].score}\n"
    if game.victory_lap and winning_team == game.teams[0].name:
        winstring += f"{winning_team} wins with a victory lap!"
    elif winning_team == game.teams[0].name:
        winstring += f"{winning_team} wins with a partial victory lap!"
    else:
        winstring += f"{winning_team} wins on the road!"

    embed = discord.Embed(color=discord.Color.dark_purple(), title=title_string)
    embed.add_field(name="Final score:", value=winstring, inline=False)
    embed.add_field(name=f"{game.teams[1].name} pitcher:", value=game.teams[1].pitcher.name)
    embed.add_field(name=f"{game.teams[0].name} pitcher:", value=game.teams[0].pitcher.name)
    embed.set_footer(text=game.weather.emoji + game.weather.name)
    return embed

async def update_loop():
    while True:
        for game in gamesarray:
            if game.message_queue:
                await game.inter.channel.send(game.message_queue.pop(0))
                await asyncio.sleep(1)
            else:
                if game.over:
                    await game.inter.channel.send(f"{game.inter.user.mention}'s game just ended.", embed=game_over_embed(game))
                    gamesarray.remove(game)
                    break
                game.plate_appearance()


COMMANDS = [startgame, startrandomgame]