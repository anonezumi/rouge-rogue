import json, random, os, math, jsonpickle, weather, player, team, discord, asyncio, gametext, urllib
import database as db
import onomancer as ono
from gametext import base_string, appearance_outcomes, game_strings_base
from uuid import uuid4
from client import client, setupmessages

data_dir = "data"
games_config_file = os.path.join(data_dir, "games_config.json")
gamesarray = []

def config():
    if not os.path.exists(os.path.dirname(games_config_file)):
        os.makedirs(os.path.dirname(games_config_file))
    if not os.path.exists(games_config_file):
        #generate default config
        config_dic = {
                "default_length" : 3,
                "stlat_weights" : {
                        "batting_stars" : 1, #batting
                        "pitching_stars" : 0.8, #pitching
                        "baserunning_stars" : 1, #baserunning
                        "defense_stars" : 1 #defense
                    },
                "stolen_base_chance_mod" : 1,
                "stolen_base_success_mod" : 1
            }
        with open(games_config_file, "w") as config_file:
            json.dump(config_dic, config_file, indent=4)
            return config_dic
    else:
        with open(games_config_file) as config_file:
            return json.load(config_file)


class Game(object):
    def __init__(self, team1, team2, length=None):
        self.over = False
        self.random_weather_flag = False
        self.teams = {"away" : team1, "home" : team2}
        self.inning = 1
        self.outs = 0
        self.top_of_inning = True
        self.last_update = ({},0) #this is a ({outcome}, runs) tuple
        self.play_has_begun = False
        self.owner = None
        self.victory_lap = False
        if length is not None:
            self.max_innings = length
        else:
            self.max_innings = config()["default_length"]
        self.bases = {1 : None, 2 : None, 3 : None}
        self.weather = weather.Weather(self)
        self.voice = None
        self.current_batter = None

    def occupied_bases(self):
        occ_dic = {}
        for base in self.bases.keys():
            if self.bases[base] is not None:
                occ_dic[base] = self.bases[base]
        return occ_dic

    def choose_next_batter(self):
        if self.top_of_inning:
            bat_team = self.teams["away"]
        else:
            bat_team = self.teams["home"]

        self.current_batter = bat_team.lineup[bat_team.lineup_position % len(bat_team.lineup)]
        self.weather.on_choose_next_batter(self)

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
        outcome = {}
        pitcher = self.get_pitcher()
        batter = self.get_batter()

        if self.top_of_inning:
            defender_list = self.teams["home"].lineup.copy()
        else:
            defender_list = self.teams["away"].lineup.copy()

        defender_list.append(pitcher)
        defender = random.choice(defender_list) #make pitchers field

        outcome["batter"] = batter
        outcome["pitcher"] = pitcher
        outcome["defender"] = ""

        player_rolls = {}
        player_rolls["bat_stat"] = random_star_gen("batting_stars", batter)
        player_rolls["pitch_stat"] = random_star_gen("pitching_stars", pitcher)

        self.weather.modify_atbat_stats(player_rolls)

        roll = {}
        roll["pb_system_stat"] = (random.gauss(1*math.erf((player_rolls["bat_stat"] - player_rolls["pitch_stat"])*1.5)-1.8,2.2))
        roll["hitnum"] = random.gauss(2*math.erf(player_rolls["bat_stat"]/4)-1,3)

        self.weather.modify_atbat_roll(outcome, roll, defender)

        
        if roll["pb_system_stat"] <= 0:
            outcome["ishit"] = False
            fc_flag = False
            if roll["hitnum"] < -1.5:
                outcome["outcome"] = random.choice([appearance_outcomes.strikeoutlooking, appearance_outcomes.strikeoutswinging])
            elif roll["hitnum"] < 1:
                outcome["outcome"] = appearance_outcomes.groundout
                outcome["defender"] = defender
            elif roll["hitnum"] < 4: 
                outcome["outcome"] = appearance_outcomes.flyout
                outcome["defender"] = defender
            else:
                outcome["outcome"] = appearance_outcomes.walk

            if self.bases[1] is not None and roll["hitnum"] < -2 and (self.outs != 2 or self.weather.out_extension):
                outcome["outcome"] = appearance_outcomes.doubleplay
                outcome["defender"] = ""

            #for base in self.bases.values():
                #if base is not None:
                    #fc_flag = True

            runners = [(0,self.get_batter())]
            for base in range(1,4):
                if self.bases[base] == None:
                    break
                runners.append((base, self.bases[base]))
            outcome["runners"] = runners #list of consecutive baserunners: (base number, player object)

            if self.outs < 2 and len(runners) > 1: #fielder's choice replaces not great groundouts if any forceouts are present
                def_stat = random_star_gen("defense_stars", defender)
                if -1.5 <= roll["hitnum"] and roll["hitnum"] < -0.5: #poorly hit groundouts
                    outcome["outcome"] = appearance_outcomes.fielderschoice
                    outcome["defender"] = ""
            
            if outcome["outcome"] not in [appearance_outcomes.strikeoutlooking, appearance_outcomes.strikeoutswinging] and 2.5 <= roll["hitnum"] and self.outs < 2: #well hit flyouts can lead to sacrifice flies/advanced runners
                if self.bases[2] is not None or self.bases[3] is not None:
                    outcome["advance"] = True
        else:
            outcome["ishit"] = True
            if roll["hitnum"] < 1:
                outcome["outcome"] = appearance_outcomes.single
            elif roll["hitnum"] < 2.85 or "error" in outcome.keys():
                outcome["outcome"] = appearance_outcomes.double
            elif roll["hitnum"] < 3.1:
                outcome["outcome"] = appearance_outcomes.triple
            else:
                if self.bases[1] is not None and self.bases[2] is not None and self.bases[3] is not None:
                    outcome["outcome"] = appearance_outcomes.grandslam
                else:
                    outcome["outcome"] = appearance_outcomes.homerun

        return outcome

    def thievery_attempts(self): #returns either false or "at-bat" outcome
        thieves = []
        attempts = []
        outcome = {}
        for base in self.bases.keys():
            if self.bases[base] is not None and base != 3: #no stealing home in simsim, sorry stu
                if self.bases[base+1] is None: #if there's somewhere to go
                    thieves.append((self.bases[base], base))
        for baserunner, start_base in thieves:
            stats = {
                "run_stars": random_star_gen("baserunning_stars", baserunner)*config()["stolen_base_chance_mod"],
                "def_stars": random_star_gen("defense_stars", self.get_pitcher())
            }

            self.weather.modify_steal_stats(stats)

            if stats["run_stars"] >= (stats["def_stars"] - 1.5): #if baserunner isn't worse than pitcher
                roll = random.random()
                if roll >= (-(((stats["run_stars"]+1)/14)**2)+1): #plug it into desmos or something, you'll see
                    attempts.append((baserunner, start_base))

        if len(attempts) == 0:
            return False
        else:     
            return (self.steals_check(attempts, outcome), 0) #effectively an at-bat outcome with no score

    def steals_check(self, attempts, outcome):
        if self.top_of_inning:
            defense_team = self.teams["home"]
        else:
            defense_team = self.teams["away"]

        for baserunner, start_base in attempts:
            defender = random.choice(defense_team.lineup) #excludes pitcher
            run_stat = random_star_gen("baserunning_stars", baserunner)
            def_stat = random_star_gen("defense_stars", defender)
            run_roll = random.gauss(2*math.erf((run_stat-def_stat)/4)-1,3)*config()["stolen_base_success_mod"]

            if start_base == 2:
                run_roll = run_roll * .9 #stealing third is harder
            if run_roll < 1:
                successful = False  
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1
            else:
                successful = True
                self.bases[start_base+1] = baserunner
            self.bases[start_base] = None

        self.voice.stealing(outcome, baserunner.name, base_string(start_base+1), defender.name, successful)

        self.weather.steal_post_activate(self, outcome)

        if self.outs >= 3:
            self.flip_inning()

        return outcome

    def baserunner_check(self, defender, outcome):
        def_stat = random_star_gen("defense_stars", defender)
        if outcome["outcome"] == appearance_outcomes.homerun or outcome["outcome"] == appearance_outcomes.grandslam:
            runs = 1
            for base in self.bases.values():
                if base is not None:
                    runs += 1
            self.bases = {1 : None, 2 : None, 3 : None}
            if "veil" in outcome.keys():
                if runs < 4:
                    self.bases[runs] = self.get_batter()
                else:
                    runs += 1
            return runs

        elif "advance" in outcome.keys():
            runs = 0
            if self.bases[3] is not None:
                outcome["outcome"] = appearance_outcomes.sacrifice
                self.get_batter().game_stats["sacrifices"] += 1 
                self.bases[3] = None
                runs = 1
            if self.bases[2] is not None:
                run_roll = random.gauss(2*math.erf((random_star_gen("baserunning_stars", self.bases[2])-def_stat)/4)-1,3)

                if run_roll > 2:
                    self.bases[3] = self.bases[2]
                    self.bases[2] = None
            return runs

        elif outcome["outcome"] == appearance_outcomes.fielderschoice:
            furthest_base, runner = outcome["runners"].pop() #get furthest baserunner
            self.bases[furthest_base] = None 
            outcome["fc_out"] = (runner.name, base_string(furthest_base+1)) #runner thrown out
            outcome["runner"] = runner.name
            outcome["base"] = furthest_base+1
            for index in range(0,len(outcome["runners"])):
                base, this_runner = outcome["runners"].pop()
                self.bases[base+1] = this_runner #includes batter, at base 0
            if self.bases[3] is not None and furthest_base == 1: #fielders' choice with runners on the corners
                self.bases[3] = None
                return 1
            return 0

        elif outcome["outcome"] == appearance_outcomes.groundout or outcome["outcome"] == appearance_outcomes.doubleplay:
            runs = 0
            if self.bases[3] is not None:
                runs += 1
                self.bases[3] = None
            if self.bases[2] is not None:
                run_roll = random.gauss(2*math.erf((random_star_gen("baserunning_stars", self.bases[2])-def_stat)/4)-1,3)

                if run_roll > 1.5 or outcome["outcome"] == appearance_outcomes.doubleplay: #double play gives them time to run, guaranteed
                    self.bases[3] = self.bases[2]
                    self.bases[2] = None
            if self.bases[1] is not None: #double plays set this to None before this call
                run_roll = random.gauss(2*math.erf((random_star_gen("baserunning_stars", self.bases[1])-def_stat)/4)-1,3)

                if run_roll < 2 or self.bases[2] is not None: #if runner can't make it or if baserunner blocking on second, convert to fielder's choice
                    outcome["outcome"] == appearance_outcomes.fielderschoice
                    runners = [(0,self.get_batter())]
                    for base in range(1,4):
                        if self.bases[base] == None:
                            break
                        runners.append((base, self.bases[base]))
                    outcome["runners"] = runners #rebuild consecutive runners
                    return runs + self.baserunner_check(defender, outcome) #run again as fielder's choice instead
                else:
                    self.bases[2] = self.bases[1]
                    self.bases[1] = None
            return runs

        elif outcome["ishit"]:
            runs = 0
            if outcome["outcome"] == appearance_outcomes.single:
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
                return runs

            elif outcome["outcome"] == appearance_outcomes.double:
                runs = 0
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
                return runs
                    

            elif outcome["outcome"] == appearance_outcomes.triple:
                runs = 0
                for basenum in self.bases.keys():
                    if self.bases[basenum] is not None:
                        runs += 1
                        self.bases[basenum] = None
                self.bases[3] = self.get_batter()
                return runs


    def batterup(self):
        scores_to_add = 0

        if "twopart" not in self.last_update[0]:
            result = self.at_bat()  
    
            if self.top_of_inning:
                offense_team = self.teams["away"]
                defense_team = self.teams["home"]
            else:
                offense_team = self.teams["home"]
                defense_team = self.teams["away"]

            defenders = defense_team.lineup.copy()
            defenders.append(defense_team.pitcher)
            defender = random.choice(defenders) #pitcher can field outs now :3
            result["defender"] = defender
            result["defense_team"] = defense_team
            result["offense_team"] = offense_team

            if "advance" in result.keys() and self.bases[3] is not None:
                result["outcome"] = appearance_outcomes.sacrifice
                result["runner"] = self.bases[3].name

            text_list = getattr(self.voice, result["outcome"].name)
            voice_index = random.randrange(0, len(text_list))
            result["voiceindex"] = voice_index
        else:
            result = {}

        result = self.voice.activate(self.last_update[0], result, self)

        if "twopart" not in result:
            self.weather.activate(self, result) # possibly modify result in-place

            if "text_only" in result:
                return (result, 0)  

        if "twopart" in result:
            if self.voice.post_format != []:
                format_list = []
                for extra_format in self.voice.post_format:
                    try:
                        if extra_format == "base":
                            format_list.append(base_string(result["base"]))
                        elif extra_format == "runner":
                            format_list.append(result["runner"])
                    except KeyError:
                        format_list.append("None")
                self.voice.post_format = []
                result["displaytext"] = result["displaytext"].format(*format_list)
            return (result, 0)

        if result["ishit"]: #if batter gets a hit:
            self.get_batter().game_stats["hits"] += 1
            self.get_pitcher().game_stats["hits_allowed"] += 1

            if result["outcome"] == appearance_outcomes.single:
                self.get_batter().game_stats["total_bases"] += 1               
            elif result["outcome"] == appearance_outcomes.double:
                self.get_batter().game_stats["total_bases"] += 2
            elif result["outcome"] == appearance_outcomes.triple:
                self.get_batter().game_stats["total_bases"] += 3
            elif result["outcome"] == appearance_outcomes.homerun or result["outcome"] == appearance_outcomes.grandslam:
                self.get_batter().game_stats["total_bases"] += 4
                self.get_batter().game_stats["home_runs"] += 1

            scores_to_add += self.baserunner_check(result["defender"], result)

        else: #batter did not get a hit
            if result["outcome"] == appearance_outcomes.walk:
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
            
            elif result["outcome"] == appearance_outcomes.doubleplay:
                self.get_pitcher().game_stats["outs_pitched"] += 2
                self.outs += 2
                self.bases[1] = None     
                if self.outs < 3:
                    scores_to_add += self.baserunner_check(result["defender"], result)
                    self.get_batter().game_stats["rbis"] -= scores_to_add #remove the fake rbi from the player in advance

            elif result["outcome"] == appearance_outcomes.fielderschoice or result["outcome"] == appearance_outcomes.groundout:
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1
                if self.outs < 3:
                    scores_to_add += self.baserunner_check(result["defender"], result)

            elif "advance" in result.keys() or result["outcome"] == appearance_outcomes.sacrifice:
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1
                if self.outs < 3:
                    if self.bases[3] is not None:
                        result["runner"] = self.bases[3].name
                        self.get_batter().game_stats["sacrifices"] += 1
                    scores_to_add += self.baserunner_check(result["defender"], result)

            elif result["outcome"] == appearance_outcomes.strikeoutlooking or result["outcome"] == appearance_outcomes.strikeoutswinging:
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1
                self.get_batter().game_stats["strikeouts_taken"] += 1
                self.get_pitcher().game_stats["strikeouts_given"] += 1

            else: 
                self.get_pitcher().game_stats["outs_pitched"] += 1
                self.outs += 1

        self.get_batter().game_stats["plate_appearances"] += 1
        
        if self.voice.post_format != []:
            format_list = []
            for extra_format in self.voice.post_format:
                try:
                    if extra_format == "base":
                        format_list.append(base_string(result["base"]))
                    elif extra_format == "runner":
                        format_list.append(result["runner"])
                except KeyError:
                    format_list.append("None")
            self.voice.post_format = []
            result["displaytext"] = result["displaytext"].format(*format_list)

        if self.outs < 3:
            result["offense_team"].score += scores_to_add #only add points if inning isn't over
        else:
            scores_to_add = 0
        self.get_batter().game_stats["rbis"] += scores_to_add
        self.get_pitcher().game_stats["runs_allowed"] += scores_to_add
        result["offense_team"].lineup_position += 1 #put next batter up
        self.choose_next_batter()    

        self.weather.post_activate(self, result)

        if self.outs >= 3:
            self.flip_inning()
            
         

        return (result, scores_to_add) #returns ab information and scores

    def flip_inning(self):
        for base in self.bases.keys():
            self.bases[base] = None
        self.outs = 0

        self.top_of_inning = not self.top_of_inning

        if self.random_weather_flag and self.top_of_inning:
            setattr(self, "weather", random.choice(list(weather.safe_weathers().values()))(self))

        self.weather.on_flip_inning(self)

        self.choose_next_batter()

        if self.top_of_inning:
            self.inning += 1
            if self.inning > self.max_innings and self.teams["home"].score != self.teams["away"].score: #game over
                self.over = True
                try: #if something goes wrong with OBL don't erase game
                    if self.max_innings >= 9 or self.weather.name in ["Leaf Eddies", "Torrential Downpour"]:
                        this_xvi_team = None
                        db.save_obl_results(self.teams["home"] if self.teams["home"].score > self.teams["away"].score else self.teams["away"], self.teams["home"] if self.teams["home"].score < self.teams["away"].score else self.teams["away"], xvi_team=this_xvi_team)
                except:
                    pass
                


    def end_of_game_report(self):
        return {
                "away_team" : self.teams["away"],
                "away_pitcher" : self.teams["away"].pitcher,
                "home_team" : self.teams["home"],
                "home_pitcher" : self.teams["home"].pitcher
            }

    def named_bases(self):
        name_bases = {}
        for base in range(1,4):
            if self.bases[base] is not None:
                name_bases[base] = self.bases[base].name
            else:
                name_bases[base] = None

        return name_bases


    def gamestate_update_full(self):
        self.play_has_begun = True
        attempts = self.thievery_attempts()
        if attempts == False or "twopart" in self.last_update[0]:
            self.last_update = self.batterup()
        else:
            self.last_update = attempts
        return self.gamestate_display_full()

    def gamestate_display_full(self):
        if not self.over:
            return "Still in progress."
        else:
            return f"""Game over! Final score: **{self.teams['away'].score} - {self.teams['home'].score}**"""

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
async def startgame(inter: discord.Interaction, home: str, away: str, weather_name: str = None, voice: str = None, innings: int = 9):

    if config()["game_freeze"]:
        await inter.response.send_message("Patch incoming. We're not allowing new games right now.")
        return
    
    if weather_name is not None and weather_name not in weather.all_weathers():
        await inter.response.send_message("Can't find that weather.")
        return

    if voice not in gametext.all_voices():
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

    if innings < 2 and inter.user.id not in config()["owners"]:
        await inter.response.send_message(content="Anything less than 2 innings isn't even an outing. Try again.")
        return

    if innings > 200 and inter.user.id not in config()["owners"]:
        await inter.response.send_message(content="Current inning limit is 200. That should be plenty, really.")
        return

    game = Game(home_team.finalize(), away_team.finalize(), length=innings)
    if voice is not None:
        game.voice = voice()
    
    if weather_name is not None:
        game.weather = weather.all_weathers()[weather_name](game)               

    game_task = asyncio.create_task(watch_game(inter.channel, game, user=inter.user))
    await game_task

@discord.app_commands.command()
async def startrandomgame(inter: discord.Interaction):
    if config()["game_freeze"]:
        await inter.response.send_message(content="Patch incoming. We're not allowing new games right now.")
        return

    await inter.response.send_message(content="Rolling the bones... This might take a while.")
    teamslist = team.get_all_teams()

    game = Game(random.choice(teamslist).finalize(), random.choice(teamslist).finalize())

    game_task = asyncio.create_task(watch_game(inter.channel, game, user="the winds of chaos"))
    await game_task

async def watch_game(channel, newgame, user = None, league = None):
    newgame, state_init = prepare_game(newgame)

    if league is not None:
        state_init["is_league"] = True
    else:
        state_init["is_league"] = False

    id = str(uuid4())
    ext = "?game="+id
    if league is not None:
        ext += "&league=" + urllib.parse.quote_plus(league)

    await channel.send(f"{newgame.teams['away'].name} vs. {newgame.teams['home'].name}, starting at {config()['simmadome_url']+ext}")
    gamesarray.append((newgame, channel, user, id))

def prepare_game(newgame, league = None, weather_name = None):
    if weather_name is None and newgame.weather.name == "Sunny":
        weathers = weather.all_weathers()
        newgame.weather = weathers[random.choice(list(weathers.keys()))](newgame)

    if newgame.voice is None:
        newgame.voice = random.choices(gametext.weighted_voices()[0], weights=gametext.weighted_voices()[1])[0]()

    state_init = {
        "away_name" : newgame.teams['away'].name,
        "home_name" : newgame.teams['home'].name,
        "max_innings" : newgame.max_innings,
        "update_pause" : 0,
        "top_of_inning" : True,
        "victory_lap" : False,
        "weather_emoji" : newgame.weather.emoji,
        "weather_text" : newgame.weather.name,
        "start_delay" : 5,
        "end_delay" : 9
        }

    if league is None:
        state_init["is_league"] = False
    else:
        state_init["is_league"] = True
        newgame.teams['away'].apply_team_mods(league.name)
        newgame.teams['home'].apply_team_mods(league.name)

    return newgame, state_init

def random_star_gen(key, player):
    return random.gauss(config()["stlat_weights"][key] * player.stlats[key],1)


async def game_watcher():
    while True:
        try:
            this_array = gamesarray.copy()
            for i in range(0,len(this_array)):
                game, channel, user, key = this_array[i]
                if game.over: # and ((key in main_controller.master_games_dic.keys() and main_controller.master_games_dic[key][1]["end_delay"] <= 8) or not key in main_controller.master_games_dic.keys()):                   
                    final_embed = game_over_embed(game)
                    if isinstance(user, str):
                        await channel.send(f"A game started by {user} just ended.")
                    elif user is not None:
                        await channel.send(f"{user.mention}'s game just ended.")
                    else:
                        await channel.send("A game started from this channel just ended.")                
                    await channel.send(embed=final_embed)
                    gamesarray.pop(i)
                    break
        except:
            print("something broke in game_watcher")
        await asyncio.sleep(4)

def game_over_embed(game):
    if game.inning != 2:
        title_string = f"{game.teams['away'].name} at {game.teams['home'].name} ended after {game.inning-1} innings"
    else:
        title_string = f"{game.teams['away'].name} at {game.teams['home'].name} ended after 1 inning"
    if (game.inning - 1) > game.max_innings: #if extra innings
        title_string += f" with {game.inning - (game.max_innings+1)} extra innings.\n"
    else:
        title_string += ".\n"

    winning_team = game.teams['home'].name if game.teams['home'].score > game.teams['away'].score else game.teams['away'].name
    homestring = str(game.teams["home"].score) + ("☄" if game.teams["home"].score == 16 else "")
    awaystring = ("☄" if game.teams["away"].score == 16 else "") + str(game.teams["away"].score)
    winstring = f"{awaystring} to {homestring}\n"
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


async def setup_game(channel, owner, newgame):
    newgame.owner = owner
    await channel.send(f"Game sucessfully created!\nStart any commands for this game with `{newgame.name}` so we know who's talking about what.")
    await asyncio.sleep(1)
    await channel.send("Who's pitching for the away team?")

    def input(msg):
            return msg.content.startswith(newgame.name) and msg.channel == channel #if author or willing participant and in correct channel

    while newgame.teams["home"].pitcher == None:

        def nameinput(msg):
            return msg.content.startswith(newgame.name) and msg.channel == channel #if author or willing participant and in correct channel



        while newgame.teams["away"].pitcher == None:
            try:
                namemsg = await client.wait_for('message', check=input)
                new_pitcher_name = discord.utils.escape_mentions(namemsg.content.split(f"{newgame.name} ")[1])
                if len(new_pitcher_name) > 70:
                    await channel.send("That player name is too long, chief. 70 or less.")
                else:
                    new_pitcher = player.Player(ono.get_stats(new_pitcher_name))
                    newgame.teams["away"].set_pitcher(new_pitcher)
                    await channel.send(f"{new_pitcher} {new_pitcher.star_string('pitching_stars')}, pitching for the away team!\nNow, the home team's pitcher. Same dance, folks.")
            except NameError:
                await channel.send("Uh.")

        try:
            namemsg = await client.wait_for('message', check=input)
            new_pitcher_name = discord.utils.escape_mentions(namemsg.content.split(f"{newgame.name} ")[1])
            if len(new_pitcher_name) > 70:
                await channel.send("That player name is too long, chief. 70 or less.")
            else:
                new_pitcher = player.Player(ono.get_stats(new_pitcher_name))
                newgame.teams["home"].set_pitcher(new_pitcher)
                await channel.send(f"And {new_pitcher} {new_pitcher.star_string('pitching_stars')}, pitching for the home team.")
        except:
            await channel.send("Uh.")

    #pitchers assigned!
    team_join_message = await channel.send(f"""Now, the lineups! We need somewhere between 1 and 12 batters. Cloning helps a lot with this sort of thing.
React to this message with 🔼 to have your idol join the away team, or 🔽 to have them join the home team.
You can also enter names like you did for the pitchers, with a slight difference: `away [name]` or `home [name]` instead of just the name.

Creator, type `{newgame.name} done` to finalize lineups.""")
    await team_join_message.add_reaction("🔼")
    await team_join_message.add_reaction("🔽")

    setupmessages[team_join_message] = newgame

    #emoji_task = asyncio.create_task(watch_for_reacts(team_join_message, ready, newgame))
    #msg_task = asyncio.create_task(watch_for_messages(channel, ready, newgame))
    #await asyncio.gather(
    #    watch_for_reacts(team_join_message, newgame),
    #    watch_for_messages(channel, newgame)
    #    )

    def messagecheck(msg):
        return (msg.content.startswith(newgame.name)) and msg.channel == channel and msg.author != client.user

    while not newgame.ready:
        try:
            msg = await client.wait_for('message', timeout=120.0, check=messagecheck)
        except asyncio.TimeoutError:
            await channel.send("Game timed out. 120 seconds between players is a bit much, see?")
            del setupmessages[team_join_message]
            del newgame
            return

        new_player = None
        if msg.author == newgame.owner and msg.content == f"{newgame.name} done":
            if newgame.teams['home'].finalize() and newgame.teams['away'].finalize():
                newgame.ready = True
                break
        else:
            side = None
            if msg.content.split(f"{newgame.name} ")[1].split(" ",1)[0] == "home":
                side = "home"
            elif msg.content.split(f"{newgame.name} ")[1].split(" ",1)[0] == "away":
                side = "away"

            if side is not None:
                new_player_name = discord.utils.escape_mentions(msg.content.split(f"{newgame.name} ")[1].split(" ",1)[1])
                if len(new_player_name) > 70:
                    await channel.send("That player name is too long, chief. 70 or less.")
                else:
                    new_player = player.Player(ono.get_stats(new_player_name))
        try:
            if new_player is not None:
                newgame.teams[side].add_lineup(new_player)
                await channel.send(f"{new_player} {new_player.star_string('batting_stars')} takes spot #{len(newgame.teams[side].lineup)} on the {side} lineup.")
        except:
            True

    del setupmessages[team_join_message] #cleanup!

    await channel.send("Name the away team, creator.")

    def ownercheck(msg):
        return msg.author == newgame.owner

    while newgame.teams["home"].name == None:
        while newgame.teams["away"].name == None:
            newname = await client.wait_for('message', check=ownercheck)
            if len(newname.content) < 30:
                newgame.teams['away'].name = newname.content
                await channel.send(f"Stepping onto the field, the visitors: {newname.content}!\nFinally, the home team, and we can begin.")
            else:
                await channel.send("Hey, keep these to 30 characters or less please. Discord messages have to stay short.")
        newname = await client.wait_for('message', check=ownercheck)
        if len(newname.content) < 30:
            newgame.teams['home'].name = newname.content
            await channel.send(f"Next on the diamond, your home team: {newname.content}!")
        else:
            await channel.send("Hey, keep these to 30 characters or less please. Discord messages have to stay short.")

    await asyncio.sleep(3)
    await channel.send(f"**{newgame.teams['away'].name} at {newgame.teams['home'].name}**")

    game_task = asyncio.create_task(watch_game(channel, newgame))
    await game_task

COMMANDS = [startgame, startrandomgame]