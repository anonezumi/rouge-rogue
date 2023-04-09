import random, math
from config import Outcome, base_string

class Weather:
    name = "Sunny"
    emoji = "🌞"
    duration_range = [3,5]
    out_extension = False

    def __init__(self, game):
        pass

    def __str__(self):
        return f"{self.emoji} {self.name}"

    def pre_roll(self, player_rolls):
        pass

    def post_roll(self, update, roll):
        pass

    def pre_steal_roll(self, roll):
        pass

    def post_result(self, game, update):
        pass

    def post_plate_appearance(self, game, update):
        pass

    def post_choose_next_batter(self, game):
        pass

    def pre_flip_inning(self, game):
        pass

    def modify_top_of_inning_message(self, game, text):
        return text

class Supernova(Weather):
    name = "Supernova"
    emoji = "🌟"
    duration_range = [1,2]

    def pre_roll(self, roll):
        roll["pitch_stat"] *= 0.8

class Midnight(Weather):
    name = "Midnight"
    emoji = "🕶"
    duration_range = [1,1]

    def pre_steal_roll(self, roll):
        roll["run_stars"] *= 2

class SlightTailwind(Weather):
    name = "Slight Tailwind"
    emoji = "🏌️‍♀️"
    duration_range = [1,2]
    mulligan = False

    def post_result(self, game, update):
        if not self.mulligan and update.outcome in [Outcome.K_LOOKING, Outcome.K_SWINGING, Outcome.GROUNDOUT, Outcome.FLYOUT, Outcome.FLYOUT_ADVANCE, Outcome.FIELDERS_CHOICE, Outcome.DOUBLE_PLAY, Outcome.SAC_FLY]: 
            mulligan_roll_target = -((((update.batter.stlats["batting_stars"])-5)/6)**2)+1
            if random.random() > mulligan_roll_target and update.batter.stlats["batting_stars"] <= 5:
                update.text_only = True
                update.displaytext = f"{update.batter} would have gone out, but they took a mulligan!"
                self.mulligan = True
        if self.mulligan:
            self.mulligan = False

class Starlight(Weather):
    name = "Starlight"
    emoji = "🌃"
    duration_range = [2,2]
    dragon = False

    def post_result(self, game, update):
        if update.outcome == Outcome.HOME_RUN or update.outcome == Outcome.GRAND_SLAM:
            dinger_roll = random.random()
            if "dragon" in update.batter.name.lower():
                self.dragon = True
            elif dinger_roll < 0.941:
                update.text_only = True
                update.display_text = f"{update.batter} hits a dinger, but the stars do not approve! The ball pulls foul."

    def post_plate_appearance(self, game, update):
        if update.outcome == Outcome.HOME_RUN or update.outcome == Outcome.GRAND_SLAM:
            if self.dragon:
                self.dragon = False
                update.displaytext = f"The stars enjoy watching dragons play baseball, and allow {update.batter} to hit a dinger! {update.runs} runs scored!"
            else:
                update.displaytext = f"The stars are pleased with {update.batter}, and allow a dinger! {update.runs} runs scored!"
               

class Blizzard(Weather):
    name = "Blizzard"
    emoji = "❄"
    duration_range = [2,3]

    def __init__(self, game):
        self.counter_away = random.randint(0,len(game.teams['away'].lineup)-1)
        self.counter_home = random.randint(0,len(game.teams['home'].lineup)-1)

        self.swapped_batter_data = None

    def post_result(self, game, update):        
        if self.swapped_batter_data:
            original, sub = self.swapped_batter_data
            self.swapped_batter_data = None
            update.displaytext = f"{original.name}'s hands are too cold! {sub.name} is forced to bat!"
            update.textonly = True

    def pre_flip_inning(self, game):
        if game.top_of_inning and self.counter_away < game.teams["away"].lineup_position:
            self.counter_away = self.pitcher_insert_index(game.teams["away"])

        if not game.top_of_inning and self.counter_home < game.teams["home"].lineup_position:
            self.counter_home = self.pitcher_insert_index(game.teams["home"])

    def pitcher_insert_index(self, this_team):
        rounds = math.ceil(this_team.lineup_position / len(this_team.lineup))
        position = random.randint(0, len(this_team.lineup)-1)
        return rounds * len(this_team.lineup) + position

    def post_choose_next_batter(self, game):
        if game.top_of_inning:
            bat_team = game.teams["away"]
            counter = self.counter_away
        else:
            bat_team = game.teams["home"]
            counter = self.counter_home

        if bat_team.lineup_position == counter:
            self.swapped_batter_data = (game.current_batter, bat_team.pitcher) # store this to generate the message during post_result()
            game.current_batter = bat_team.pitcher

class Twilight(Weather):
    name = "Twilight"
    emoji = "👻"
    duration_range = [2,3]
    error = False

    def post_roll(self, update, roll):
        error_line = - (math.log(update.defender.stlats["defense_stars"] + 1)/50) + 1
        if random.random() > error_line:
            self.error = True
            roll["pb_system_stat"] = 0.1

    def post_plate_appearance(self, game, update):
        if self.error:
            self.error = False
            update.displaytext = f"{update.batter}'s hit goes ethereal, and {update.defender} can't catch it! {update.batter} reaches base safely."
            if update.runs > 0:
                update.displaytext += f" {update.runs} runs scored!"

class ThinnedVeil(Weather):
    name = "Thinned Veil"
    emoji = "🌌"
    duration_range = [1,3]
    veil = False

    def post_result(self, game, update):
        if update.outcome == Outcome.HOME_RUN or update.outcome == Outcome.GRAND_SLAM:
            self.veil = True

    def post_plate_appearance(self, game, update):
        if self.veil:
            self.veil = False
            update.emoji = self.emoji
            update.displaytext += f" {update.batter}'s will manifests on {base_string(update.base)} base."

class HeatWave(Weather):
    name = "Heat Wave"
    emoji = "🌄"
    duration_range = [2,3]

    def __init__(self, game):
        self.counter_away = random.randint(2,4)
        self.counter_home = random.randint(2,4)

        self.swapped_pitcher_data = None

    def pre_flip_inning(self, game):
        original_pitcher = game.get_pitcher()
        if game.top_of_inning:
            bat_team = game.teams["home"]
            counter = self.counter_home
        else:
            bat_team = game.teams["away"]
            counter = self.counter_away

        if game.inning == counter:
            if game.top_of_inning:
                self.counter_home = self.counter_home - (self.counter_home % 5) + 5 + random.randint(1,4) #rounds down to last 5, adds up to next 5. then adds a random number 2<=x<=5 to determine next pitcher                       
            else:
                self.counter_away = self.counter_away - (self.counter_away % 5) + 5 + random.randint(1,4)      

            #swap, accounting for teams where where someone's both batter and pitcher
            tries = 0
            while game.get_pitcher() == original_pitcher and tries < 3:
                bat_team.set_pitcher(use_lineup = True)
                tries += 1
            if game.get_pitcher() != original_pitcher:
                self.swapped_pitcher_data = (original_pitcher, game.get_pitcher())

    def modify_top_of_inning_message(self, game, text):
        if self.swapped_pitcher_data:
            original, sub = self.swapped_pitcher_data
            self.swapped_pitcher_data = None
            return text + f' {original} is exhausted from the heat. {sub} is forced to pitch!'
             
                

class Drizzle(Weather):
    name = "Drizzle"
    emoji = "🌧"
    duration_range = [2,3]

    def pre_flip_inning(self, game):
        if game.top_of_inning:
            next_team = "away"
        else:
            next_team = "home"

        lineup = game.teams[next_team].lineup
        game.bases[2] = lineup[(game.teams[next_team].lineup_position-1) % len(lineup)]

    def modify_top_of_inning_message(self, game, text):
        if game.top_of_inning:
            next_team = "away"
        else:
            next_team = "home"

        placed_player = game.teams[next_team].lineup[(game.teams[next_team].lineup_position-1) % len(game.teams[next_team].lineup)]

        return text + f' Due to inclement weather, {placed_player.name} is placed on second base.'

class Breezy(Weather):
    name = "Breezy"
    emoji = "🎐"
    duration_range = [1,3]

    def __init__(self, game):       
        self.activation_chance = 0.08

    def post_result(self, game, update):
        if random.random() < self.activation_chance:
            teamtype = random.choice(["away","home"])
            team = game.teams[teamtype]
            player = random.choice(team.lineup)
            player.stlats["batting_stars"] = player.stlats["pitching_stars"]
            player.stlats["pitching_stars"] = player.stlats["baserunning_stars"]
            old_player_name = player.name

            if not hasattr(player, "stat_name"):
                player.stat_name = old_player_name

            if ' ' in player.name:
                names = player.name.split(" ")
                try:
                    first_first_letter = names[0][0]
                    last_first_letter = names[-1][0]
                    names[0] = last_first_letter + names[0][1:]
                    names[-1] = first_first_letter + names[-1][1:]
                    player.name = ' '.join(names)
                except:
                    first_letter = player.name[0]
                    last_letter = player.name[-1]
                    player.name = last_letter + player.name[1:-1] + first_letter
            else:
                #name is one word, so turn 'bartholemew' into 'martholemeb'
                first_letter = player.name[0]
                last_letter = player.name[-1]
                player.name = last_letter + player.name[1:-1] + first_letter

            book_adjectives = ["action-packed", "historical", "mystery", "thriller", "horror", "sci-fi", "fantasy", "spooky","romantic"]
            book_types = ["novel", "novella", "poem", "anthology", "fan fiction", "autobiography"]
            book = "{} {}".format(random.choice(book_adjectives),random.choice(book_types))

            update.displaytext = "{} stopped to enjoy a {} in the nice breeze! {} is now {}!".format(old_player_name, book, old_player_name, player.name)
            update.text_only = True

class MeteorShower(Weather):
    name = "Meteor Shower"
    emoji = "🌠"
    duration_range = [1,3]

    def __init__(self, game):
        self.activation_chance = 0.13

    def post_result(self, game, update):
        if random.random() < self.activation_chance and game.occupied_bases() != {}:
            base, runner = random.choice(list(game.occupied_bases().items()))
            runner = game.bases[base]
            game.bases[base] = None

            if game.top_of_inning:
                bat_team = game.teams["away"]
            else:
                bat_team = game.teams["home"]

            bat_team.score += 1
            update.text = f"{runner.name} wished upon one of the shooting stars, and was warped to None base!! 1 runs scored!"
            update.text_only = True

class Hurricane(Weather):
    name = "Hurricane"
    emoji = "🌀"
    duration_range = [1,1]

    def __init__(self, game):
        self.swaplength = random.randint(2,4)
        self.swapped = False

    def pre_flip_inning(self, game):
        if game.top_of_inning and (game.inning % self.swaplength) == 0:
            self.swaplength = random.randint(2,4)
            self.swapped = True

    def modify_top_of_inning_message(self, game, text):
        if self.swapped:
            game.teams["home"].score, game.teams["away"].score = (game.teams["away"].score, game.teams["home"].score) #swap scores
            self.swapped = False
            return text + " The hurricane rages on, flipping the scoreboard!"

class Tornado(Weather):
    name = "Tornado"
    emoji = "🌪"
    duration_range = [1,2]

    def __init__(self, game):
        self.activation_chance = 0.33
        self.counter = 0

    def post_result(self, game, update):
        if self.counter == 0 and random.random() < self.activation_chance and game.occupied_bases() != {}:
            runners = list(game.bases.values())
            current_runners = runners.copy()
            self.counter = 5
            while runners == current_runners and self.counter > 0:
                random.shuffle(runners)
                self.counter -= 1
            for index in range(1,4):
                game.bases[index] = runners[index-1]

            update.displaytext = f"The tornado sweeps across the field and pushes {'the runners' if len(game.occupied_bases().values())>1 else list(game.occupied_bases().values())[0].name} to a different base!"
            update.text_only = True
            self.counter = 2

        elif self.counter > 0:
            self.counter -= 1

class Downpour(Weather):
    name = "Torrential Downpour"
    emoji = '⛈'
    duration_range = [1,1]

    def __init__(self, game):
        self.target = game.max_innings
        self.name = f"Torrential Downpour: {self.target}"
        self.emoji = '⛈'
        

    def pre_flip_inning(self, game):
        high_score = game.teams["home"].score if game.teams["home"].score > game.teams["away"].score else game.teams["away"].score
        if high_score >= self.target and game.teams["home"].score != game.teams["away"].score:
            game.max_innings = game.inning
        else:
            game.max_innings = game.inning + 1

    def modify_top_of_inning_message(self, game, text):
        if game.teams["away"].score >= self.target: #if the away team has met the target
            if game.teams["home"].score == game.teams["away"].score: #if the teams are tied
                return "The gods demand a victor. Play on."
            return f"The gods are pleased, but demand more from {game.teams['home'].name}. Take the field."
        return "The gods are not yet pleased. Play continues through the storm."

class SummerMist(Weather):
    name = "Summer Mist"
    emoji = "🌁"
    duration_range = [1,3]
    substances = ["yellow mustard", "cat fur", "dread", "caramel", "nacho cheese", "mud", "dirt", "justice", "a green goo", "water, probably", "antimatter", "something not of this world", "live ferrets", "snow", "leaves",
                 "yarn", "seaweed", "sawdust", "stardust", "code fragments", "milk", "lizards", "a large tarp", "feathers"]
    mist = False

    def __init__(self, game):
        self.missing_players = {game.teams["home"].name: None, game.teams["away"].name: None}
        self.text = ""

    def post_result(self, game, update):
        if update.outcome in [Outcome.FLYOUT, Outcome.GROUNDOUT, Outcome.SAC_FLY, Outcome.FLYOUT_ADVANCE]:
            roll = random.random()
            if roll < .4: #get lost
                self.mist = True
                team = update.offense_team
                self.text = f" {update.batter} gets lost in the mist on the way back to the dugout."
                if self.missing_players[team.name] is not None:
                    self.text += f" {self.missing_players[team.name].name} wanders back, covered in {random.choice(self.substances)}!"
                    team.lineup[team.lineup_position % len(team.lineup)] = self.missing_players[team.name]
                else:
                    team.lineup.pop(team.lineup_position % len(team.lineup))
                self.missing_players[team.name] = update.batter

    def post_plate_appearance(self, game, update):
        if self.mist:
            self.mist = False
            update.emoji = self.emoji
            update.displaytext += self.text
            self.text = ""

class LeafEddies(Weather):
    name = "Leaf Eddies"
    emoji = "🍂"
    duration_range = [1,2]

    leaves = ["orange", "brown", "yellow", "red", "fake", "real", "green", "magenta", "violet", "black", "infrared", "cosmic", "microscopic", "celestial", "spiritual", "ghostly", "transparent"]
    eddy_types = [" cloud", " small tornado", "n orb", " sheet", "n eddy", " smattering", " large number", " pair"]
    out_counter = 0
    sent = False
    first = True
    

    def __init__(self, game):
        self.name = f"Leaf Eddies: {game.max_innings*3}"
        self.original_innings = game.max_innings
        game.max_innings = 1
        self.inning_text = "The umpires have remembered their jobs. They shoo the defenders off the field!"

    def post_result(self, game, update):
        if game.inning == 1:
            if self.out_counter % 3 == 0 and not self.out_counter == 0 and not self.sent:
                if self.first:
                    self.first = False
                    updatetext = "The leaves have distracted the umpires, and they've been unable to keep track of outs!"               
                else:
                    leaf = random.sample(self.leaves, 2)
                    eddy = random.choice(self.eddy_types)
                    updatetext = f"A{eddy} of {leaf[0]} and {leaf[1]} leaves blows through, and the umpires remain distracted!"
                self.sent = True
                update.displaytext = updatetext
                update.text_only = True
        else:
            game.outs = 2

    def post_plate_appearance(self, game, update):
        if game.inning == 1:
            if game.outs > 0:
                self.out_counter += game.outs
                game.outs = 0
                self.sent = False
                if self.out_counter < (self.original_innings * 3):
                    self.name = f"Leaf Eddies: {self.original_innings*3-self.out_counter}"
                else:
                    self.name = "Leaf Eddies"
                    self.out_counter = 0
                    game.outs = 3
        elif game.teams["home"].score != game.teams["away"].score:
            game.outs = 3
            if game.top_of_inning:
                game.inning += 1
                game.top_of_inning = False

    def modify_top_of_inning_message(self, game, text):
        if game.inning == 1:
            self.name = f"Leaf Eddies: {self.original_innings*3-self.out_counter}"
        else:
            self.name = "Leaf Eddies: Golden Run"
            self.inning_text = "SUDDEN DEATH ⚠"
        return self.inning_text

class Smog(Weather):
    name = "Smog"
    emoji = "🚌"
    duration_range = [1,2]

    def __init__(self, game):
        game.random_weather_flag = True
        setattr(game, "weather", random.choice(list(safe_weathers().values()))(game))

class Dusk(Weather):
    name = "Dusk"
    emoji = "🌆"
    duration_range = [2,3]

    def __init__(self, game):
        for team in game.teams.values():
            random.shuffle(team.lineup)

    def post_result(self, game, update):
        if update.outcome in [Outcome.K_LOOKING, Outcome.K_SWINGING, Outcome.GROUNDOUT, Outcome.FLYOUT, Outcome.FLYOUT_ADVANCE, Outcome.FIELDERS_CHOICE, Outcome.DOUBLE_PLAY, Outcome.SAC_FLY]:
            update.offense_team.lineup_position -= 1
            if game.outs >= 2 or (game.outs >= 1 and update.outcome == Outcome.DOUBLE_PLAY):
                update.displaytext += random.choice([" A shade returns to the dugout with them, waiting.",
                                                        " They return to the dugout alongside a shade.",
                                                        " A shade waits patiently."])
            else:
                if random.random() < 0.01:
                    update.displaytext += " But it refused."
                else:
                    update.displaytext += random.choice([" They leave a shade behind!",
                                                            " A shade of the self remains.",
                                                            " They leave a shade in the light of the setting sun.",
                                                            " They return to the dugout, but their shade remains.",
                                                            " They leave a shade at the plate for another plate appearance.",
                                                            " Their shade refuses to leave the plate, and shoulders the bat."])

class Runoff(Weather):
    name = "Runoff"
    emoji = "🏔️"
    duration_range = [2,4]

    def __init__(self, game):
        self.overflow_out = False
        self.out_extension = True

    def post_plate_appearance(self, game, update):
        if game.outs >= 4:
            self.overflow_out = True

    def pre_flip_inning(self, game):
        if self.overflow_out:
            game.outs += 1

    def modify_top_of_inning_message(self, game, text):
        if self.overflow_out:
            self.overflow_out = False
            return text + " The extra out from last inning carries over in the runoff!"

def all_weathers():
    weathers_dic = {
            "Supernova" : Supernova,
            "Midnight": Midnight,
            "Slight Tailwind": SlightTailwind,
            "Blizzard": Blizzard,
            "Twilight" : Twilight, 
            "Thinned Veil" : ThinnedVeil,
            "Heat Wave" : HeatWave,
            "Drizzle" : Drizzle,
            "Breezy": Breezy,
            "Starlight" : Starlight,
            "Meteor Shower" : MeteorShower,
            "Hurricane" : Hurricane,
            "Tornado" : Tornado,
            "Torrential Downpour" : Downpour,
            "Summer Mist" : SummerMist,
            "Leaf Eddies" : LeafEddies,
            "Smog" : Smog,
            "Dusk" : Dusk,
            "Runoff" :  Runoff,
            "Sunny" : Weather
        }
    return weathers_dic

def safe_weathers():
    """weathers safe to swap in mid-game"""
    weathers_dic = {
            "Supernova" : Supernova,
            "Midnight": Midnight,
            "Slight Tailwind": SlightTailwind,
            "Twilight" : Twilight, 
            "Thinned Veil" : ThinnedVeil,
            "Drizzle" : Drizzle,
            "Breezy": Breezy,
            "Starlight" : Starlight,
            "Meteor Shower" : MeteorShower,
            "Hurricane" : Hurricane,
            "Tornado" : Tornado,
            "Summer Mist" : SummerMist,
            "Dusk" : Dusk,
            "Sunny" : Weather
        }
    return weathers_dic

class WeatherChains():
    light = [SlightTailwind, Twilight, Breezy, Drizzle, SummerMist, LeafEddies, Runoff] #basic starting points for weather, good comfortable spots to return to
    magic = [Twilight, ThinnedVeil, MeteorShower, Starlight, Dusk] #weathers involving breaking the fabric of spacetime
    sudden = [Tornado, Hurricane, Twilight, Starlight, Midnight, Downpour, Smog] #weathers that always happen and leave over 1-3 games
    disaster = [Hurricane, Tornado, Downpour, Blizzard] #storms
    aftermath = [Midnight, Starlight, MeteorShower, SummerMist, Dusk, Runoff] #calm epilogues

    dictionary = {
            #Supernova : (magic + sudden + disaster, None), supernova happens leaguewide and shouldn't need a chain, but here just in case
            Midnight : ([SlightTailwind, Breezy, Drizzle, Starlight, MeteorShower, HeatWave, SummerMist],[2,2,2,4,4,1,2]),
            SlightTailwind : ([Breezy, Drizzle, LeafEddies, Smog, Tornado], [3,3,3,3,1]),
            Blizzard : ([Midnight, Starlight, MeteorShower, Twilight, Downpour, Dusk], [2,2,2,2,4,2]),
            Twilight : ([ThinnedVeil, Midnight, MeteorShower, SlightTailwind, SummerMist], [2,4,2,1,2]),
            ThinnedVeil : (light, None),
            HeatWave : ([Tornado, Hurricane, SlightTailwind, Breezy, SummerMist, Dusk],[4,4,1,1,2,1]),
            Drizzle : ([Hurricane, Downpour, Blizzard],[2,2,1]),
            Breezy : ([Drizzle, HeatWave, Blizzard, Smog, Tornado], [3,3,1,3,1]),
            Starlight : ([SlightTailwind, Twilight, Breezy, Drizzle, ThinnedVeil, HeatWave], None),
            MeteorShower : ([Starlight, ThinnedVeil, HeatWave, Smog], None),
            Hurricane : ([LeafEddies, Midnight, Starlight, MeteorShower, Twilight, Downpour], [3,2,2,2,2,4]),
            Tornado : ([LeafEddies, Midnight, Starlight, MeteorShower, Twilight, Downpour],[3,2,2,2,2,4]),
            SummerMist : ([Drizzle, Breezy, Hurricane, Downpour, Dusk],[2, 1, 1, 1,4]),
            LeafEddies : ([Breezy, Tornado, SummerMist, ThinnedVeil, Smog], None),
            Downpour : (aftermath, None),
            Smog : (disaster + [Drizzle], None),
            Dusk : ([ThinnedVeil, Midnight, MeteorShower, Starlight], [4,2,2,3]),
            Runoff : (magic, None)
        }

    chains = [
            [Hurricane, Drizzle, Hurricane]
        ]

    def chain_weather(weather_instance):
        #weather_type = type(weather_instance)
        weather_type = weather_instance
        options, weight = WeatherChains.dictionary[weather_type]
        return random.choices(options, weights = weight)[0]

    def parent_weathers(weather_type):
        parents = []
        for this_weather, (children, _) in WeatherChains.dictionary.items():
            if weather_type in children:
                parents.append(this_weather)
        return parents

    def starting_weather():
        return random.choice(WeatherChains.light + WeatherChains.magic)

    def debug_weathers():
        names = ["a.txt", "b.txt", "c.txt"]
        for name in names:
            current = random.choice(list(all_weathers().values()))
            out = ""
            for i in range(0,50):
                out += f"{current.name} {current.emoji}\n"
                current = WeatherChains.chain_weather(current)
            
            with open("data/"+name, "w", encoding='utf-8') as file:
                file.write(out)
