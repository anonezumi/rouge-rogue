import discord, os, json, logging, enum

DATA_DIR = "data"

class Outcome(enum.Enum):
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

base_string = ["None", "first", "second", "third", "home"]

logging.basicConfig(filename="rougerogue.log", encoding="utf-8", level=logging.DEBUG)

client = discord.Client(intents=(discord.Intents.default()))
config_filename = os.path.join(DATA_DIR, "config.json")

if not os.path.exists(os.path.dirname(config_filename)):
    os.makedirs(os.path.dirname(config_filename))
if not os.path.exists(config_filename):
    #generate default config
    config_dic = {
            "token": "",
            "owners": [
                0000
                ],
            "game_freeze": 0,
            "default_length": 9,
            "roll_weights": {},
            "roll_thresholds": {}
        }
    with open(config_filename, "w") as config_file:
        json.dump(config_dic, config_file, indent=4)
        print("please fill in bot token and any bot admin discord ids to the new config.json file!")
        quit()

config = json.load(open(config_filename))