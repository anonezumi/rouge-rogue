import discord, os, json

DATA_DIR = "data"

client = discord.Client(intents=(discord.Intents.all()))
config_filename = os.path.join(DATA_DIR, "config.json")
setupmessages = {}

if not os.path.exists(os.path.dirname(config_filename)):
    os.makedirs(os.path.dirname(config_filename))
if not os.path.exists(config_filename):
    #generate default config
    config_dic = {
            "token" : "",
            "owners" : [
                0000
                ],
            "ea" : [
                0000
                ],
            "blacklist" : [
                0000
                ],
            "simmadome_url" : "",
            "game_freeze" : 0
        }
    with open(config_filename, "w") as config_file:
        json.dump(config_dic, config_file, indent=4)
        print("please fill in bot token and any bot admin discord ids to the new config.json file!")
        quit()

config = json.load(open(config_filename))