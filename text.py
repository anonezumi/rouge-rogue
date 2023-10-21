import json, discord

ALL_TEXT = json.load(open("text.json"))

def gettext(id: str):
    ids = id.split(".")
    token = ALL_TEXT
    while ids != []:
        try:
            token = token[ids.pop(0)]
        except KeyError:
            return f"[{id}]"
    return token

@discord.app_commands.command()
async def help(inter: discord.Interaction, topic: str = "default"):
    try:
        result = gettext(f"help.{topic}")
        inter.response.send_message(result)
    except:
        inter.response.send_message(gettext("error.help.invalid_topic"))

COMMANDS = [help]