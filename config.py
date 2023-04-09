import discord, os, json
from enum import Enum

DATA_DIR = "data"

all_voices = json.load(open("voices.json"))
base_string = ["None", "first", "second", "third", "home"]

class Outcome(Enum):
    K_LOOKING = "strikeoutlooking"
    K_SWINGING = "strikeoutswinging"
    GROUNDOUT = "groundout"
    FLYOUT = "flyout"
    FLYOUT_ADVANCE = "flyoutadvance"
    FIELDERS_CHOICE = "fielderschoice"
    DOUBLE_PLAY = "doubleplay"
    SAC_FLY = "sacrifice"
    WALK = "walk"
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    HOME_RUN = "homerun"
    GRAND_SLAM = "grandslam"

client = discord.Client(intents=(discord.Intents.all()))
config_filename = os.path.join(DATA_DIR, "config.json")

if not os.path.exists(os.path.dirname(config_filename)):
    os.makedirs(os.path.dirname(config_filename))
if not os.path.exists(config_filename):
    #generate default config
    config_dic = {
            "token" : "",
            "owners" : [
                0000
                ],
            "game_freeze" : 0,
            "default_length" : 3,
            "stlat_weights" : {
                    "batting_stars" : 1,
                    "pitching_stars" : 0.8,
                    "baserunning_stars" : 1,
                    "defense_stars" : 1
                },
            "stolen_base_chance_mod" : 1,
            "stolen_base_success_mod" : 1
        }
    with open(config_filename, "w") as config_file:
        json.dump(config_dic, config_file, indent=4)
        print("please fill in bot token and any bot admin discord ids to the new config.json file!")
        quit()

config = json.load(open(config_filename))