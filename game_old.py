import random, math, weather, player, team, discord, asyncio, json, time, voice
import database as db
from config import config, base_string, Outcome

gamesarray = []

class Update():
    def __init__(self):
        self.outcome = None
        self.runners = []
        self.batter = None
        self.pitcher = None
        self.defender = None
        self.displaytext = ""
        self.emoji = ""
        self.offense_team = None
        self.defense_team = None
        self.runner = None
        self.text_only = False

class Game(object):
    def __init__(self, team1, team2, inter, length=None, voice=None, weather_name="Sunny"):
        self.over = False
        self.random_weather_flag = False
        self.teams = {"away" : team1, "home" : team2}
        self.inter = inter
        self.inning = 1
        self.outs = 0
        self.top_of_inning = True
        self.last_update = Update()
        self.play_has_begun = False
        self.victory_lap = False
        if length is not None:
            self.max_innings = length
        else:
            self.max_innings = config["default_length"]
        self.bases = {1 : None, 2 : None, 3 : None}
        self.voice = voice
        self.current_batter = None
        self.weather = weather.all_weathers()[weather_name](self)
        self.message_queue = []

    def choose_next_batter(self):
        if self.top_of_inning:
            bat_team = self.teams["away"]
        else:
            bat_team = self.teams["home"]

        self.current_batter = bat_team.lineup[bat_team.lineup_position % len(bat_team.lineup)]
        self.weather.post_choose_next_batter(self)

    def get_batter(self):
        if self.current_batter == None:
            self.choose_next_batter()
        return self.current_batter

    def get_pitcher(self):
        if self.top_of_inning:
            return self.teams["home"].pitcher
        else:
            return self.teams["away"].pitcher

    def at_bat(self):
        update = Update()
        pitcher = self.get_pitcher()
        batter = self.get_batter()

        if self.top_of_inning:
            defender_list = self.teams["home"].lineup
        else:
            defender_list = self.teams["away"].lineup

        defender = random.choice(defender_list)

        update.batter = batter
        update.pitcher = pitcher
        update.defender = defender

        player_rolls = {}
        player_rolls["bat_stat"] = random_star_gen("batting_stars", batter)
        player_rolls["pitch_stat"] = random_star_gen("pitching_stars", pitcher)

        self.weather.pre_roll(player_rolls)

        roll = {}
        roll["pb_system_stat"] = (random.gauss(1*math.erf((player_rolls["bat_stat"] - player_rolls["pitch_stat"])*1.5)-1.8,2.2))
        roll["hitnum"] = random.gauss(2*math.erf(player_rolls["bat_stat"]/4)-1,3)

        self.weather.post_roll(update, roll)

        
        if roll["pb_system_stat"] <= 0:
            runners = [(0,self.get_batter())]
            for base in range(1,4):
                if self.bases[base] == None:
                    break
                runners.append((base, self.bases[base]))
            update.runners = runners #list of consecutive baserunners: (base number, player object)

            if roll["hitnum"] < -2 and self.bases[1] is not None and (self.outs != 2 or self.weather.out_extension):
                update.outcome = Outcome.DOUBLE_PLAY
            elif roll["hitnum"] < -1.5:
                update.outcome = random.choice([Outcome.K_LOOKING, Outcome.K_SWINGING])
            elif roll["hitnum"] < -0.5 and self.outs < 2 and len(runners) > 1:
                update.outcome = Outcome.FIELDERS_CHOICE
            elif roll["hitnum"] < 1:
                update.outcome = Outcome.GROUNDOUT
            elif roll["hitnum"] > 2.5 and self.outs < 2 and self.bases[2] is not None:
                update.outcome = Outcome.FLYOUT_ADVANCE
            elif roll["hitnum"] > 2.5 and self.outs < 2 and self.bases[3] is not None:
                update.outcome = Outcome.SAC_FLY
            elif roll["hitnum"] < 4: 
                update.outcome = Outcome.FLYOUT
            else:
                update.outcome = Outcome.WALK
        else:
            if roll["hitnum"] < 1:
                update.outcome = Outcome.SINGLE
            elif roll["hitnum"] < 2.85:
                update.outcome = Outcome.DOUBLE
            elif roll["hitnum"] < 3.1:
                update.outcome = Outcome.TRIPLE
            else:
                if self.bases[1] is not None and self.bases[2] is not None and self.bases[3] is not None:
                    update.outcome = Outcome.GRAND_SLAM
                else:
                    update.outcome = Outcome.HOME_RUN
        return update

    def thievery_attempts(self): #returns either false or "at-bat" outcome
        thieves = []
        attempts = []
        for base in self.bases.keys():
            if self.bases[base] is not None and base != 3: #no stealing home in simsim, sorry stu
                if self.bases[base+1] is None: #if there's somewhere to go
                    thieves.append((self.bases[base], base))
        for baserunner, start_base in thieves:
            stats = {
                "run_stars": random_star_gen("baserunning_stars", baserunner)*config["stolen_base_chance_mod"],
                "def_stars": random_star_gen("defense_stars", self.get_pitcher())
            }

            self.weather.pre_steal_roll(stats)

            if stats["run_stars"] >= (stats["def_stars"] - 1.5): #if baserunner isn't worse than pitcher
                roll = random.random()
                if roll >= (-(((stats["run_stars"]+1)/14)**2)+1): #plug it into desmos or something, you'll see
                    attempts.append((baserunner, start_base))

        if len(attempts) == 0:
            return False
        else:     
            return self.steals_check(attempts)

    def steals_check(self, attempts):
        if self.top_of_inning:
            defense_team = self.teams["home"]
        else:
            defense_team = self.teams["away"]

        results_text = []

        for baserunner, start_base in attempts:
            defender = random.choice(defense_team.lineup) #excludes pitcher
            run_stat = random_star_gen("baserunning_stars", baserunner)
            def_stat = random_star_gen("defense_stars", defender)
            run_roll = random.gauss(2*math.erf((run_stat-def_stat)/4)-1,3)*config["stolen_base_success_mod"]
            up = Update()
            up.defender = defender
            up.runner = baserunner
            up.base_string = base_string[start_base + 1]

            if start_base == 2:
                run_roll = run_roll * .9 #stealing third is harder
            if run_roll < 1:
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1
                results_text.append(random.choice(self.voice["steal_caught"]).format(up))
            else:
                self.bases[start_base+1] = baserunner
                results_text.append(random.choice(self.voice["steal_success"]).format(up))
            self.bases[start_base] = None
            if self.outs >= 3:
                self.flip_inning()
                return results_text

        return results_text

    def baserunner_check(self, defender, update):
        def_stat = random_star_gen("defense_stars", defender)
        runs = 0
        if update.outcome == Outcome.HOME_RUN or update.outcome == Outcome.GRAND_SLAM:
            runs = 1
            for base in self.bases.values():
                if base is not None:
                    runs += 1
            self.bases = {1 : None, 2 : None, 3 : None}
        elif update.outcome == Outcome.SAC_FLY:
            self.get_batter().game_stats["sacrifices"] += 1 
            self.bases[3] = None
            runs = 1
        elif update.outcome == Outcome.FLYOUT_ADVANCE:
            run_roll = random.gauss(2*math.erf((random_star_gen("baserunning_stars", self.bases[2])-def_stat)/4)-1,3)

            if run_roll > 2:
                self.bases[3] = self.bases[2]
                self.bases[2] = None
                update.outcome = Outcome.FLYOUT # TODO: until i add new text
            else:
                update.outcome = Outcome.FLYOUT
        elif update.outcome == Outcome.FIELDERS_CHOICE:
            furthest_base, runner = update.runners.pop() #get furthest baserunner
            self.bases[furthest_base] = None 
            update.fc_out = (runner.name, base_string[furthest_base+1]) #runner thrown out
            update.runner = runner.name
            update.base = furthest_base + 1
            for index in range(0,len(update.runners)):
                base, this_runner = update.runners.pop()
                self.bases[base+1] = this_runner #includes batter, at base 0
            if self.bases[3] is not None and furthest_base == 1: #fielders' choice with runners on the corners
                self.bases[3] = None
                runs = 1
        elif update.outcome == Outcome.FIELDERS_CHOICE or update.outcome == Outcome.DOUBLE_PLAY:
            if self.bases[3] is not None:
                runs += 1
                self.bases[3] = None
            if self.bases[2] is not None:
                run_roll = random.gauss(2*math.erf((random_star_gen("baserunning_stars", self.bases[2])-def_stat)/4)-1,3)

                if run_roll > 1.5 or update.outcome == Outcome.DOUBLE_PLAY: #double play gives them time to run, guaranteed
                    self.bases[3] = self.bases[2]
                    self.bases[2] = None
            if self.bases[1] is not None: #double plays set this to None before this call
                run_roll = random.gauss(2*math.erf((random_star_gen("baserunning_stars", self.bases[1])-def_stat)/4)-1,3)

                if run_roll < 2 or self.bases[2] is not None: #if runner can't make it or if baserunner blocking on second, convert to fielder's choice
                    update.outcome = Outcome.FIELDERS_CHOICE
                    runners = [(0,self.get_batter())]
                    for base in range(1,4):
                        if self.bases[base] == None:
                            break
                        runners.append((base, self.bases[base]))
                    update.runners = runners #rebuild consecutive runners
                    return runs + self.baserunner_check(defender, update) #run again as fielder's choice instead
                else:
                    self.bases[2] = self.bases[1]
                    self.bases[1] = None
        elif update.outcome == Outcome.SINGLE:
            if self.bases[3] is not None:
                runs += 1
                self.bases[3] = None
            if self.bases[2] is not None:
                run_roll = random.gauss(math.erf(random_star_gen("baserunning_stars", self.bases[2])-def_stat)-.5,1.5)

                if run_roll > 0:
                    runs += 1
                else:
                    self.bases[3] = self.bases[2]
                self.bases[2] = None
            if self.bases[1] is not None:
                if self.bases[3] is None:
                    run_roll = random.gauss(math.erf(random_star_gen("baserunning_stars", self.bases[1])-def_stat)-.5,1.5)

                    if run_roll > 0.75:
                        self.bases[3] = self.bases[1]
                    else:
                        self.bases[2] = self.bases[1]
                else:
                    self.bases[2] = self.bases[1]
                self.bases[1] = None

            self.bases[1] = self.get_batter()
        elif update.outcome == Outcome.DOUBLE:
            if self.bases[3] is not None:
                runs += 1
                self.bases[3] = None
            if self.bases[2] is not None:
                runs += 1
                self.bases[2] = None
            if self.bases[1] is not None:
                run_roll = random.gauss(math.erf(random_star_gen("baserunning_stars", self.bases[1])-def_stat)-.5,1.5)

                if run_roll > 1:
                    runs += 1
                    self.bases[1] = None
                else:
                    self.bases[3] = self.bases[1]
                    self.bases[1] = None
            self.bases[2] = self.get_batter()
        elif update.outcome == Outcome.TRIPLE:
            for basenum in self.bases.keys():
                if self.bases[basenum] is not None:
                    runs += 1
                    self.bases[basenum] = None
            self.bases[3] = self.get_batter()
        return runs


    def batterup(self):
        scores_to_add = 0
        update = self.at_bat()  

        if self.top_of_inning:
            offense_team = self.teams["away"]
            defense_team = self.teams["home"]
        else:
            offense_team = self.teams["home"]
            defense_team = self.teams["away"]

        defender = random.choice(defense_team.lineup)
        update.defender = defender
        update.defense_team = defense_team
        update.offense_team = offense_team
        text = random.choice(self.voice[update.outcome.value])
        if isinstance(text, list):
            update.displaytext = [t.format(update) for t in text]
        else:
            update.displaytext = [text.format(update)]

        self.weather.post_result(self, update)

        if update.text_only:
            return update

        if update.outcome in [Outcome.SINGLE, Outcome.DOUBLE, Outcome.TRIPLE, Outcome.HOME_RUN, Outcome.GRAND_SLAM]: #if batter gets a hit:
            self.get_batter().game_stats["hits"] += 1
            self.get_pitcher().game_stats["hits_allowed"] += 1

            if update.outcome == Outcome.SINGLE:
                self.get_batter().game_stats["total_bases"] += 1               
            elif update.outcome == Outcome.DOUBLE:
                self.get_batter().game_stats["total_bases"] += 2
            elif update.outcome == Outcome.TRIPLE:
                self.get_batter().game_stats["total_bases"] += 3
            elif update.outcome == Outcome.HOME_RUN or update.outcome == Outcome.GRAND_SLAM:
                self.get_batter().game_stats["total_bases"] += 4
                self.get_batter().game_stats["home_runs"] += 1

            scores_to_add += self.baserunner_check(update.defender, update)

        else: #batter did not get a hit
            if update.outcome == Outcome.WALK:
                walkers = [(0,self.get_batter())]
                for base in range(1,4):
                    if self.bases[base] == None:
                        break
                    walkers.append((base, self.bases[base]))
                for i in range(0, len(walkers)):
                    this_walker = walkers.pop()
                    if this_walker[0] == 3:
                        self.bases[3] = None
                        scores_to_add += 1
                    else:
                        self.bases[this_walker[0]+1] = this_walker[1] #this moves all consecutive baserunners one forward

                self.get_batter().game_stats["walks_taken"] += 1
                self.get_pitcher().game_stats["walks_allowed"] += 1
            
            elif update.outcome == Outcome.DOUBLE_PLAY:
                self.get_pitcher().game_stats["outs_pitched"] += 2
                self.outs += 2
                self.bases[1] = None     
                if self.outs < 3:
                    scores_to_add += self.baserunner_check(update.defender, update)
                    self.get_batter().game_stats["rbis"] -= scores_to_add #remove the fake rbi from the player in advance

            elif update.outcome == Outcome.FIELDERS_CHOICE or update.outcome == Outcome.GROUNDOUT:
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1
                if self.outs < 3:
                    scores_to_add += self.baserunner_check(update.defender, update)

            elif update.outcome == Outcome.SAC_FLY or update.outcome == Outcome.FLYOUT_ADVANCE:
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1
                if self.outs < 3:
                    if self.bases[3] is not None:
                        update.runner = self.bases[3].name
                        self.get_batter().game_stats["sacrifices"] += 1
                    scores_to_add += self.baserunner_check(update.defender, update)

            elif update.outcome == Outcome.K_LOOKING or update.outcome == Outcome.K_SWINGING:
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1
                self.get_batter().game_stats["strikeouts_taken"] += 1
                self.get_pitcher().game_stats["strikeouts_given"] += 1

            else: 
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1

        self.get_batter().game_stats["plate_appearances"] += 1

        update.offense_team.score += scores_to_add
        self.get_batter().game_stats["rbis"] += scores_to_add
        self.get_pitcher().game_stats["runs_allowed"] += scores_to_add
        update.offense_team.lineup_position += 1 #put next batter up
        self.choose_next_batter()

        self.weather.post_plate_appearance(self, update)

        return update

    def flip_inning(self):
        for base in self.bases.keys():
            self.bases[base] = None
        self.outs = 0

        self.top_of_inning = not self.top_of_inning

        if self.random_weather_flag and self.top_of_inning:
            self.weather = random.choice(list(weather.safe_weathers().values()))(self)

        self.weather.pre_flip_inning(self)

        self.choose_next_batter()

        if self.top_of_inning:
            self.inning += 1
            if self.inning > self.max_innings and self.teams["home"].score != self.teams["away"].score:
                self.over = True
            else:
                text = f"End of inning {self.inning - 1}."
                text = self.weather.modify_top_of_inning_message(self, text)
                self.message_queue += [text]

    def gamestate_update_full(self):
        self.play_has_begun = True
        attempts = self.thievery_attempts()
        if attempts == False:
            self.last_update = self.batterup()
            self.message_queue += self.last_update.displaytext
            if self.outs >= 3:
                self.flip_inning()
        else:
            self.message_queue += attempts

    def add_stats(self):
        players = self.get_stats()
        db.add_stats(players)

    def get_stats(self):
        players = []
        for this_player in self.teams["away"].lineup:
            players.append((this_player.stat_name, this_player.game_stats))
        for this_player in self.teams["home"].lineup:
            players.append((this_player.stat_name, this_player.game_stats))
        players.append((self.teams["home"].pitcher.stat_name, self.teams["home"].pitcher.game_stats))
        players.append((self.teams["away"].pitcher.stat_name, self.teams["away"].pitcher.game_stats))
        return players

    def get_team_specific_stats(self):
        players = {
            self.teams["away"].name : [],
            self.teams["home"].name : []
            }
        for this_player in self.teams["away"].lineup:
            try:
                players[self.teams["away"].name].append((this_player.stat_name, this_player.game_stats))
            except AttributeError:
                players[self.teams["away"].name].append((this_player.name, this_player.game_stats))
        for this_player in self.teams["home"].lineup:
            try:
                players[self.teams["home"].name].append((this_player.stat_name, this_player.game_stats))
            except AttributeError:
                players[self.teams["home"].name].append((this_player.name, this_player.game_stats))
        try:
            players[self.teams["home"].name].append((self.teams["home"].pitcher.stat_name, self.teams["home"].pitcher.game_stats))
        except AttributeError:
            players[self.teams["home"].name].append((self.teams["home"].pitcher.name, self.teams["home"].pitcher.game_stats))
        try:
            players[self.teams["away"].name].append((self.teams["away"].pitcher.stat_name, self.teams["away"].pitcher.game_stats))
        except AttributeError:
            players[self.teams["away"].name].append((self.teams["away"].pitcher.name, self.teams["away"].pitcher.game_stats))
        return players

@discord.app_commands.command()
async def startgame(inter: discord.Interaction, home: str, away: str, weather_name: str = "None", voice: str = None, innings: int = 9):
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

    game = Game(home_team.finalize(), away_team.finalize(), inter, length=innings, voice=voice)

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

    await newgame.inter.response.send_message(f"{newgame.teams['away'].name} vs. {newgame.teams['home'].name}, starting now!")
    gamesarray.append(newgame)

def random_star_gen(key, player):
    return random.gauss(config["stat_weights"][key] * player.stats[key],1)

def game_over_embed(game):
    title_string = f"{game.teams['away'].name} at {game.teams['home'].name} ended after {game.inning-1} innings"
    if (game.inning - 1) > game.max_innings: #if extra innings
        title_string += f" with {game.inning - (game.max_innings+1)} extra innings.\n"
    else:
        title_string += ".\n"

    winning_team = game.teams['home'].name if game.teams['home'].score > game.teams['away'].score else game.teams['away'].name
    winstring = f"{game.teams['away'].score} to {game.teams['home'].score}\n"
    if game.victory_lap and winning_team == game.teams['home'].name:
        winstring += f"{winning_team} wins with a victory lap!"
    elif winning_team == game.teams['home'].name:
        winstring += f"{winning_team} wins with a partial victory lap!"
    else:
        winstring += f"{winning_team} wins on the road!"

    embed = discord.Embed(color=discord.Color.dark_purple(), title=title_string)
    embed.add_field(name="Final score:", value=winstring, inline=False)
    embed.add_field(name=f"{game.teams['away'].name} pitcher:", value=game.teams['away'].pitcher.name)
    embed.add_field(name=f"{game.teams['home'].name} pitcher:", value=game.teams['home'].pitcher.name)
    embed.set_footer(text=game.weather.emoji + game.weather.name)
    return embed

async def update_loop():
    while True:
        for game in gamesarray:
            if not game.message_queue:
                if game.over:
                    await game.inter.channel.send(f"{game.inter.user.mention}'s game just ended.", embed=game_over_embed(game))
                    gamesarray.remove(game)
                    break
                game.gamestate_update_full()
            await game.inter.channel.send(game.message_queue.pop(0))

        await asyncio.sleep(4)

COMMANDS = [startgame, startrandomgame]