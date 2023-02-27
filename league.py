import time, asyncio, json, jsonpickle, random, math, os
import league_storage as league_db
from weather import WeatherChains, all_weathers
from itertools import chain
from copy import deepcopy
from discord import Embed, Color
from uuid import uuid4

data_dir = "data"
league_dir = "leagues"

            
class StartLeagueCommand(Command):
    name = "startleague"
    template = "m;startleague [league name]\n[games per hour]"
    description = """Optional flags for the first line: `--queue X` or `-q X` to play X number of series before stopping; `--autopostseason` will automatically start postseason at the end of the season.
Starts games from a league with a given name, provided that league has been saved on the website and has been claimed using claimleague. The games per hour sets how often the games will start (e.g. GPH 2 will start games at X:00 and X:30). By default it will play the entire season followed by the postseason and then stop but this can be customized using the flags.
Not every team will play every series, due to how the scheduling algorithm is coded but it will all even out by the end."""

    async def execute(self, msg, command, flags):
        autoplay = -1
        autopost = False
        nopost = False

        if config()["game_freeze"]:
            raise CommandError("Patch incoming. We're not allowing new games right now.")

        league_name = command.split("-")[0].split("\n")[0].strip()

        for flag in flags:
            if flag[0] == "q":
                try:
                    autoplay = int(flag[1])
                    if autoplay <= 0:
                        raise ValueError
                except ValueError:
                    raise CommandError("Sorry boss, the queue flag needs a natural number. Any whole number over 0 will do just fine.")
            elif flag[0] == "n": #noautopostseason
                await msg.channel.send("Automatic postseason is now disabled by default! No need for this flag in the future. --autopostseason (or -a) will *enable* autopostseason, should you want it.")
            elif flag[0] == "a": #autopostseason
                await msg.channel.send("We'll automatically start postseason for you, when we get there.")
                autopost = True
            elif flag[0] == "s": #skippostseason
                await msg.channel.send("We'll **skip postseason** for you! Make sure you wanted to do this.")
                autopost = True
                nopost = True
            else:
                raise CommandError("One or more of those flags wasn't right. Try and fix that for us and we'll see about sorting you out.")

        try:
            gph = int(command.split("\n")[1].strip())
            if gph < 1 or gph > 12:
                raise ValueError
        except ValueError:
            raise CommandError("Chief, we need a games per hour number between 1 and 12. We think that's reasonable.")
        except IndexError:
            raise CommandError("We need a games per hour number in the second line.")

        if league_exists(league_name):
            league = league.load_league_file(league_name)
            if autoplay == -1 and not autopost:
                autoplay = int(list(league.schedule.keys())[-1]) - league.day_to_series_num(league.day) + 1           
            if nopost:
                league.postseason = False

            if league.historic:
                raise CommandError("That league is done and dusted, chief. Sorry.")
            for active_league in active_leagues:
                if active_league.name == league.name:
                    raise CommandError("That league is already running, boss. Patience is a virtue, you know.")
            if (league.owner is not None and msg.author.id in league.owner) or msg.author.id in config()["owners"] or league.owner is None:
                league.autoplay = autoplay
                league.games_per_hour = gph
                if str(league.day_to_series_num(league.day)) not in league.schedule.keys():
                    await league_postseason(msg.channel, league)
                elif league.day % league.series_length == 1:
                    await start_league_day(msg.channel, league)
                else:
                    await start_league_day(msg.channel, league, partial = True)
            else:
                raise CommandError("You don't have permission to manage that league.")
        else:
            raise CommandError("Couldn't find that league, boss. Did you save it on the website?")

class LeagueSubscribeCommand(Command):
    name = "leaguesub"
    template = "m;leaguesub [league name]"
    description = "Posts all league feed events to this channel, in addition to the channel the league was started in. Run again to unsubscribe."

    async def execute(self, msg, command, flags):
        league_name = command.strip()
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            if msg.channel.id in league.subbed_channels:
                league.subbed_channels.pop(league.subbed_channels.index(msg.channel.id))
                await msg.channel.send("You're off the mailing list, boss. We promise.")
            else:
                league.subbed_channels.append(msg.channel.id)
                await msg.channel.send(f"Thanks for signing up to the {league_name} newsletter.")
            league.save_league(league)
        else:
            raise CommandError("That league doesn't exist, boss.")

class LeagueDisplayCommand(Command):
    name = "leaguestandings"
    template = "m;leaguestandings\n[league name]"
    description = "Displays the current standings for the given league. Use `--season X` or `-s X` to get standings from season X of that league."

    async def execute(self, msg, command, flags):
        try:
            if league_exists(command.split("\n")[1].strip()):
                try:
                    league = league.load_league_file(command.split("\n")[1].strip())
                except IndexError:
                    raise CommandError("League name goes on the second line now, boss.")

                for flag in flags:
                    if flag[0] == "s":
                        try:
                            season_num = int(flag[1])
                            await msg.channel.send(embed=league.past_standings(season_num))
                            return
                        except ValueError:
                            raise CommandError("Give us a proper number, boss.")
                        except TypeError:
                            raise CommandError("That season hasn't been played yet, chief.")

                await msg.channel.send(embed=league.standings_embed())
            else:
                raise CommandError("Can't find that league, boss.")
        except IndexError:
            raise CommandError("League name goes on the second line now, boss.")

class LeagueLeadersCommand(Command):
    name = "leagueleaders"
    template = "m;leagueleaders [league name]\n[stat name/abbreviation]"
    description = "Displays a league's leaders in the given stat. A list of the allowed stats can be found on the github readme."

    async def execute(self, msg, command, flags):
        if league_exists(command.split("\n")[0].strip()):
            league = league.load_league_file(command.split("\n")[0].strip())
            stat_name = command.split("\n")[1].strip()
            season_num = None

            for flag in flags:
                if flag[0] == "s":
                    try:
                        season_num = int(flag[1])
                        return
                    except ValueError:
                        raise CommandError("Give us a proper number, boss.")

            try:
                stat_embed = league.stat_embed(stat_name, season_num)
            except IndexError:
                raise CommandError("Nobody's played enough games to get meaningful stats in that category yet, chief. Try again after the next game or two.")
            except ValueError:
                raise CommandError("That season hasn't been played yet.")

            if stat_embed is None:
                raise CommandError("We don't know what that stat is, chief.")
            try:
                await msg.channel.send(embed=stat_embed)
                return
            except:
                raise CommandError("Nobody's played enough games to get meaningful stats in that category yet, chief. Try again after the next game or two.")

        raise CommandError("Can't find that league, boss.")

class LeagueDivisionDisplayCommand(Command):
    name = "divisionstandings"
    template = "m;divisionstandings [league name]\n[division name]"
    description = "Displays the current standings for the given division in the given league."

    async def execute(self, msg, command, flags):
        if league_exists(command.split("\n")[0].strip()):
            league = league.load_league_file(command.split("\n")[0].strip())
            division_name = command.split("\n")[1].strip()
            division = None
            for subleague in iter(league.league.keys()):
                for div in iter(league.league[subleague].keys()):
                    if div == division_name:
                        division = league.league[subleague][div]
            if division is None:
                raise CommandError("Chief, that division doesn't exist in that league.")
            try:
                await msg.channel.send(embed=league.standings_embed_div(division, division_name))
            except:
                raise CommandError("Something went wrong, boss. Check your staging.")
        else:
            raise CommandError("Can't find that league, boss.")

class LeagueWildcardCommand(Command):
    name = "leaguewildcard"
    template = "m;leaguewildcard [league name]"
    description = "Displays the current wildcard race for the given league, if the league has wildcard slots."

    async def execute(self, msg, command, flags):
        if league_exists(command.strip()):
            league = league.load_league_file(command.strip())
            if league.constraints["wild_cards"] > 0:
                await msg.channel.send(embed=league.wildcard_embed())
            else:
                raise CommandError("That league doesn't have wildcards, boss.")
        else:
            raise CommandError("Can't find that league, boss.")

class LeaguePauseCommand(Command):
    name = "pauseleague"
    template = "m;pauseleague [league name]"
    description = "Tells a currently running league to stop running after the current series."

    async def execute(self, msg, command, flags):
        league_name = command.strip()
        for active_league in active_leagues:
            if active_league.name == league_name:
                if (active_league.owner is not None and msg.author.id in active_league.owner) or msg.author.id in config()["owners"]:
                    active_league.autoplay = 0
                    await msg.channel.send(f"Loud and clear, chief. {league_name} will stop after this series is over.")
                    return
                else:
                    raise CommandError("You don't have permission to manage that league.")
        raise CommandError("That league either doesn't exist or isn't running.")

class LeagueClaimCommand(Command):
    name = "claimleague"
    template = "m;claimleague [league name]"
    description = "Claims an unclaimed league. Do this as soon as possible after creating the league, or it will remain unclaimed."

    async def execute(self, msg, command, flags):
        league_name = command.strip()
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            if league.owner is None:
                league.owner = [msg.author.id]
                league.save_league(league)
                await msg.channel.send(f"The {league.name} commissioner is doing a great job. That's you, by the way.")
                return
            else:
                raise CommandError("That league has already been claimed!")
        else:
            raise CommandError("Can't find that league, boss.")

class LeagueAddOwnersCommand(Command):
    name = "addleagueowner"
    template = "m;addleagueowner [league name]\n[user mentions]"
    description = "Adds additional owners to a league."

    async def execute(self, msg, command, flags):
        league_name = command.split("\n")[0].strip()
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            if (league.owner is not None and msg.author.id in league.owner) or (league.owner is not None and msg.author.id in config()["owners"]):
                for user in msg.mentions:
                    if user.id not in league.owner:
                        league.owner.append(user.id)
                league.save_league(league)
                await msg.channel.send(f"The new {league.name} front office is now up and running.")
                return
            else:
                raise CommandError(f"That league isn't yours, boss.")
        else:
            raise CommandError("Can't find that league, boss.")
            
class LeagueScheduleCommand(Command):
    name = "leagueschedule"
    template = "m;leagueschedule [league name]"
    description = "Sends an embed with the given league's schedule for the next 4 series."

    async def execute(self, msg, command, flags):
        league_name = command.split("\n")[0].strip()
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            current_series = league.day_to_series_num(league.day)
            if str(current_series+1) in league.schedule.keys():
                sched_embed = discord.Embed(title=f"{league.name}'s Schedule:", color=discord.Color.magenta())
                days = [0,1,2,3]
                for day in days:
                    embed_title = f"Days {((current_series+day-1)*league.series_length) + 1} - {(current_series+day)*(league.series_length)}"
                    parts = 1
                    if str(current_series+day) in league.schedule.keys():
                        schedule_text = ""
                        teams = league.team_names_in_league()
                        for game in league.schedule[str(current_series+day)]:
                            emojis = ""
                            for day_offset in range((current_series+day - 1)*league.series_length, (current_series+day)*(league.series_length)):
                                try:
                                    emojis += weather.all_weathers()[league.weather_forecast[game[1]][day_offset]].emoji + " "
                                except:
                                    False
                            schedule_text += f"**{game[0]}** @ **{game[1]}** {emojis}\n"

                            if len(schedule_text) >= 900:
                                embed_title += f" Part {parts}"
                                sched_embed.add_field(name=embed_title, value=schedule_text, inline = False)
                                parts += 1
                                embed_title = f"Days {((current_series+day-1)*league.series_length) + 1} - {(current_series+day)*(league.series_length)} Part {parts}"
                                schedule_text = ""

                            teams.pop(teams.index(game[0]))
                            teams.pop(teams.index(game[1]))
                        if len(teams) > 0:
                            schedule_text += "Resting:\n"
                            for team in teams:
                                schedule_text += f"**{team}**\n"
                                if len(schedule_text) >= 900:
                                    embed_title += f" Part {parts}"
                                    sched_embed.add_field(name=embed_title, value=schedule_text, inline = False)
                                    parts += 1
                                    embed_title = f"Days {((current_series+day-1)*league.series_length) + 1} - {(current_series+day)*(league.series_length)} Part {parts}"
                                    schedule_text = ""

                        sched_embed.add_field(name=embed_title, value=schedule_text, inline = False)
                await msg.channel.send(embed=sched_embed)
            else:
                raise CommandError("That league's already finished with this season, boss.")
        else:
            raise CommandError("We can't find that league. Typo?")

class LeagueTeamScheduleCommand(Command):
    name = "teamschedule"
    template = "m;teamschedule [league name]\n[team name]"
    description = "Sends an embed with the given team's schedule in the given league for the next 7 series."

    async def execute(self, msg, command, flags):
        league_name = command.split("\n")[0].strip()
        team_name = command.split("\n")[1].strip()
        team = get_team_fuzzy_search(team_name)
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            current_series = league.day_to_series_num(league.day)

            if team.name not in league.team_names_in_league():
                raise CommandError("Can't find that team in that league, chief.")

            if str(current_series+1) in league.schedule.keys():
                sched_embed = discord.Embed(title=f"{team.name}'s Schedule for the {league.name}:", color=discord.Color.purple())
                days = [0,1,2,3,4,5,6]
                for day in days:
                    if str(current_series+day) in league.schedule.keys():
                        schedule_text = ""

                        
                        for game in league.schedule[str(current_series+day)]:
                            if team.name in game:
                                emojis = ""
                                for day_offset in range((current_series+day - 1)*league.series_length, (current_series+day)*(league.series_length)):
                                    emojis += weather.all_weathers()[league.weather_forecast[game[1]][day_offset]].emoji + " "
                                schedule_text += f"**{game[0]}** @ **{game[1]}** {emojis}"
                        if schedule_text == "":
                            schedule_text += "Resting"
                        sched_embed.add_field(name=f"Days {((current_series+day-1)*league.series_length) + 1} - {(current_series+day)*(league.series_length)}", value=schedule_text, inline = False)
                await msg.channel.send(embed=sched_embed)
            else:
                raise CommandError("That league's already finished with this season, boss.")
        else:
            raise CommandError("We can't find that league. Typo?")
            
class LeagueRegenerateScheduleCommand(Command):
    name = "leagueseasonreset"
    template = "m;leagueseasonreset [league name]"
    description = "Completely scraps the given league's current season, resetting everything to day 1 of the current season. Requires ownership."

    async def execute(self, msg, command, flags):
        league_name = command.split("\n")[0].strip()
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            if (league.owner is not None and msg.author.id in league.owner) or (league.owner is not None and msg.author.id in config()["owners"]):
                await msg.channel.send("You got it, boss. Give us two seconds and a bucket of white-out.")
                season_restart(league)
                league.season -= 1
                league.season_reset()               
                await asyncio.sleep(1)
                await msg.channel.send("Done and dusted. Go ahead and start the league again whenever you want.")
                return
            else:
                raise CommandError("That league isn't yours, boss.")
        else:
            raise CommandError("We can't find that league. Yay?")

class LeagueForceStopCommand(Command):
    name = "leagueforcestop"
    template = "m;leagueforcestop [league name]"
    description = "Halts a league and removes it from the list of currently running leagues. To be used in the case of crashed loops."

    def isauthorized(self, user):
        return user.id in config()["owners"]

    async def execute(self, msg, command, flags):
        league_name = command.split("\n")[0].strip()
        for index in range(0,len(active_leagues)):
            if active_leagues[index].name == league_name:
                active_leagues.pop(index)
                await msg.channel.send("League halted, boss. We hope you did that on purpose.")
                return
        raise CommandError("That league either doesn't exist or isn't in the active list. So, huzzah?")

class LeagueReplaceTeamCommand(Command):
    name = "leaguereplaceteam"
    template = "m;leaguereplaceteam [league name]\n[team to remove]\n[team to add]"
    description = "Adds a team to a league, removing the old one in the process. Can only be executed by a league owner, and only before the start of a new season."
         
    async def execute(self, msg, command, flags):
        league_name = command.split("\n")[0].strip()
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            if league.day != 1:
                await msg.channel.send("That league hasn't finished its current season yet, chief. Either reset it, or be patient.")
                return
            if (league.owner is not None and msg.author.id in league.owner) or (league.owner is not None and msg.author.id in config()["owners"]):
                try:
                    team_del = get_team_fuzzy_search(command.split("\n")[1].strip())
                    team_add = get_team_fuzzy_search(command.split("\n")[2].strip())
                except IndexError:
                    raise CommandError("Three lines, boss. Make sure you give us the team to remove, then the team to add.")
                if team_add.name == team_del.name:
                    raise CommandError("Quit being cheeky. The teams have to be different.")

                if team_del is None or team_add is None:
                    raise CommandError("We couldn't find one or both of those teams, boss. Try again.")

                subleague, division = league.find_team(team_del)               

                if subleague is None or division is None:
                    raise CommandError("That first team isn't in that league, chief. So, that's good, right?")

                if league.find_team(team_add)[0] is not None:
                    raise CommandError("That second team is already in that league, chief. No doubles.")

                for index in range(0, len(league.league[subleague][division])):
                    if league.league[subleague][division][index].name == team_del.name:
                        league.league[subleague][division].pop(index)
                        league.league[subleague][division].append(team_add)
                league.schedule = {}
                league.generate_schedule()
                league.save_league_as_new(league)
                await msg.channel.send(embed=league.standings_embed())
                await msg.channel.send("Paperwork signed, stamped, copied, and faxed up to the goddess. Xie's pretty quick with this stuff.")
            else:
                raise CommandError("That league isn't yours, chief.")
        else:
            raise CommandError("We can't find that league.")

class LeagueSwapTeamCommand(Command):
    name = "leagueswapteams"
    template = "m;leagueswapteams [league name]\n[team a]\n[team b]"
    description = "Swaps two teams in any divisions or conferences of your league."

    async def execute(self, msg, command, flags):
        league_name = command.split("\n")[0].strip()
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            if league.day != 1:
                await msg.channel.send("That league hasn't finished its current season yet, chief. Either reset it, or be patient.")
                return
            if (league.owner is not None and msg.author.id in league.owner) or (league.owner is not None and msg.author.id in config()["owners"]):
                try:
                    team_a = get_team_fuzzy_search(command.split("\n")[1].strip())
                    team_b = get_team_fuzzy_search(command.split("\n")[2].strip())
                except IndexError:
                    raise CommandError("Three lines, boss. Make sure you give us the team to remove, then the team to add.")
                if team_a.name == team_b.name:
                    raise CommandError("Quit being cheeky. The teams have to be different.")

                if team_a is None or team_b is None:
                    raise CommandError("We couldn't find one or both of those teams, boss. Try again.")

                a_subleague, a_division = league.find_team(team_a)               
                b_subleague, b_division = league.find_team(team_b)

                if a_subleague is None or b_subleague is None:
                    raise CommandError("One of those teams isn't in the league. Try leaguereplaceteam instead.")

                for index in range(0, len(league.league[a_subleague][a_division])):
                    if league.league[a_subleague][a_division][index].name == team_a.name:
                        a_index = index
                for index in range(0, len(league.league[b_subleague][b_division])):
                    if league.league[b_subleague][b_division][index].name == team_b.name:
                        b_index = index

                league.league[a_subleague][a_division][a_index] = team_b
                league.league[b_subleague][b_division][b_index] = team_a
                league.schedule = {}
                league.generate_schedule()
                league.save_league_as_new(league)
                await msg.channel.send(embed=league.standings_embed())
                await msg.channel.send("Paperwork signed, stamped, copied, and faxed up to the goddess. Xie's pretty quick with this stuff.")
            else:
                raise CommandError("That league isn't yours, chief.")
        else:
            raise CommandError("We can't find that league.")


class LeagueRenameCommand(Command):
    name = "leaguerename"
    template = "m;leaguerename [league name]\n[old conference/division name]\n[new conference/division name]"
    description = "Changes the name of an existing conference or division. Can only be executed by a league owner, and only before the start of a new season."
         
    async def execute(self, msg, command, flags):
        league_name = command.split("\n")[0].strip()
        if league_exists(league_name):
            league = league.load_league_file(league_name)
            if league.day != 1:
                raise CommandError("That league hasn't finished its current season yet, chief. Either reset it, or be patient.")
            if (league.owner is not None and msg.author.id in league.owner) or (league.owner is not None and msg.author.id in config()["owners"]):
                try:
                    old_name = command.split("\n")[1].strip()
                    new_name = command.split("\n")[2].strip()
                except IndexError:
                    raise CommandError("Three lines, boss. Make sure you give us the old name, then the new name, on their own lines.")

                if old_name == new_name:
                    raise CommandError("Quit being cheeky. They have to be different names, clearly.")


                found = False
                for subleague in league.league.keys():
                    if subleague == new_name:
                        found = True
                        break
                    for division in league.league[subleague]:
                        if division == new_name:
                            found = True
                            break
                if found:
                    raise CommandError(f"{new_name} is already present in that league, chief. They have to be different.")

                found = False
                for subleague in league.league.keys():
                    if subleague == old_name:
                        league.league[new_name] = league.league.pop(old_name)
                        found = True
                        break
                    for division in league.league[subleague]:
                        if division == old_name:
                            league.league[subleague][new_name] = league.league[subleague].pop(old_name)
                            found = True
                            break
                if not found:
                    raise CommandError(f"We couldn't find {old_name} anywhere in that league, boss.")
                league.save_league_as_new(league)
                await msg.channel.send(embed=league.standings_embed())
                await msg.channel.send("Paperwork signed, stamped, copied, and faxed up to the goddess. Xie's pretty quick with this stuff.")
            else:
                raise CommandError("That league isn't yours, chief.")
        else:
            raise CommandError("We can't find that league.")


class StartTournamentCommand(Command):
    name = "starttournament"
    template = """m;starttournament
    [tournament name]
    [list of teams, each on a new line]"""
    description = "Starts a randomly seeded tournament with the provided teams, automatically adding byes as necessary. All series have a 5 minute break between games and by default there is a 10 minute break between rounds. The current tournament format is:\nBest of 5 until the finals, which are Best of 7."

    async def execute(self, msg, command, flags):
        round_delay = 10
        series_length = 5
        finals_series_length = 7
        rand_seed = True
        pre_seeded = False

        list_of_team_names = command.split("\n")[2:]

        if config()["game_freeze"]:
            raise CommandError("Patch incoming. We're not allowing new games right now.")

        for flag in flags:
            if flag[0] == "r": #rounddelay
                try:
                    round_delay = int(flag[1])
                except ValueError:
                    raise CommandError("The delay between rounds should be a whole number.")
                if round_delay < 1 or round_delay > 120:
                    raise CommandError("The delay between rounds has to  bebetween 1 and 120 minutes.")
            elif flag[0] == "b": #bestof
                try:
                    series_length = int(flag[1])
                    if series_length % 2 == 0 or series_length < 0:
                        raise ValueError
                except ValueError:
                    raise CommandError("Series length has to be an odd positive integer.")
                if msg.author.id not in config()["owners"] and series_length > 21:
                    raise CommandError("That's too long, boss. We have to run patches *some* time.")
                if len(list_of_team_names) == 2:
                    raise CommandError("--bestof is only for non-finals matches! You probably want --finalsbestof, boss. -f works too, if you want to pay respects.")
            elif flag[0] == "f": #pay respects (finalsbestof)
                try:
                    finals_series_length = int(flag[1])
                    if finals_series_length % 2 == 0 or finals_series_length < 0:
                        raise ValueError
                except ValueError:
                    raise CommandError("Finals series length has to be an odd positive integer.")
                if msg.author.id not in config()["owners"] and finals_series_length > 21:
                    raise CommandError("That's too long, boss. We have to run patches *some* time.")
            elif flag[0] == "s": #seeding
                if flag[1] == "stars":
                    rand_seed = False
                elif flag[1] == "given":
                    rand_seed = False
                    pre_seeded = True
                elif flag[1] == "random":
                    pass
                else:
                    raise CommandError("Valid seeding types are: 'random' (default), 'stars', and 'given'.")
            else:
                raise CommandError("One or more of those flags wasn't right. Try and fix that for us and we'll see about sorting you out.")

        tourney_name = command.split("\n")[1]
        team_dic = {}
        for name in list_of_team_names:
            team = get_team_fuzzy_search(name.strip())
            if team == None:
                raise CommandError(f"We couldn't find {name}. Try again?")
            add = True
            for extant_team in team_dic.keys():
                if extant_team.name == team.name:
                    add = False
            if add:
                team_dic[team] = {"wins": 0}

        channel = msg.channel

        if len(team_dic) < 2:
            await msg.channel.send("One team does not a tournament make.")
            return

        tourney = league.Tournament(tourney_name, team_dic, series_length = series_length, finals_series_length = finals_series_length, secs_between_rounds = round_delay * 60)
        tourney.build_bracket(random_sort = rand_seed)
   
        await start_tournament_round(channel, tourney)

class League(object):
    def __init__(self, name):
        self.name = name
        self.historic = False
        self.owner = None
        self.season = 1
        self.autoplay = -1
        self.champion = None
        self.weather_forecast = {}
        self.weather_override = None #set to a weather for league-wide weather effects
        self.last_weather_event_day = 0
        self.weather_event_duration = 0
        self.postseason = True
        self.subbed_channels = []

    def setup(self, league_dic, division_games = 1, inter_division_games = 1, inter_league_games = 1, games_per_hour = 2):
        self.league = league_dic # { subleague name : { division name : [team object] } }
        self.constraints = {
            "division_games" : division_games,
            "inter_div_games" : inter_division_games,
            "inter_league_games" : inter_league_games,
            "division_leaders" : 0,
            "wild_cards" : 0
            }
        self.day = 1
        self.schedule = {}
        self.series_length = 3 #can be changed
        self.game_length = None
        self.active = False
        self.games_per_hour = games_per_hour

    def season_reset(self):
        self.season += 1
        self.day = 1
        self.champion = None
        self.schedule = {}
        self.generate_schedule()
        save_league(self)

    def add_stats_from_game(self, players_dic):
        league_db.add_stats(self.name, players_dic)

    def update_standings(self, results_dic):
        league_db.update_standings(self.name, results_dic)

    def last_series_check(self):
        return str(math.ceil((self.day)/self.series_length) + 1) not in self.schedule.keys()

    def day_to_series_num(self, day):
        return math.ceil((self.day)/self.series_length)

    def tiebreaker_required(self):
        standings = {}
        matchups = []
        tournaments = []
        for team_name, wins, losses, run_diff in league_db.get_standings(self.name):
            standings[team_name] = {"wins" : wins, "losses" : losses, "run_diff" : run_diff}

        for subleague in iter(self.league.keys()):
            team_dic = {}          
            subleague_array = []
            wildcard_leaders = []
            for division in iter(self.league[subleague].keys()):
                division_standings = []
                division_standings += self.division_standings(self.league[subleague][division], standings)
                division_leaders = division_standings[:self.constraints["division_leaders"]]
                for division_team, wins, losses, diff, gb in division_standings[self.constraints["division_leaders"]:]:
                    if division_team.name != division_leaders[-1][0].name and standings[division_team.name]["wins"] == standings[division_leaders[-1][0].name]["wins"]:
                        matchups.append((division_team, division_standings[self.constraints["division_leaders"]-1][0], f"{division} Tiebreaker"))

                this_div_wildcard = [this_team for this_team, wins, losses, diff, gb in self.division_standings(self.league[subleague][division], standings)[self.constraints["division_leaders"]:]]
                subleague_array += this_div_wildcard
            if self.constraints["wild_cards"] > 0:
                wildcard_standings = self.division_standings(subleague_array, standings)
                wildcard_leaders = wildcard_standings[:self.constraints["wild_cards"]]
                for wildcard_team, wins, losses, diff, gb in wildcard_standings[self.constraints["wild_cards"]:]:
                    if wildcard_team.name != wildcard_leaders[-1][0].name and standings[wildcard_team.name]["wins"] == standings[wildcard_leaders[-1][0].name]["wins"]:
                        matchups.append((wildcard_team, wildcard_standings[self.constraints["wild_cards"]-1][0], f"{subleague} Wildcard Tiebreaker"))
        
        for team_a, team_b, type in matchups:
            tourney = Tournament(f"{self.name} {type}",{team_a : {"wins" : 1}, team_b : {"wins" : 0}}, finals_series_length=1, secs_between_games=int(3600/self.games_per_hour), secs_between_rounds=int(7200/self.games_per_hour))
            tourney.build_bracket(by_wins = True)
            tourney.league = self
            tournaments.append(tourney)
        return tournaments

    def find_team(self, team_search):
        for subleague in iter(self.league.keys()):
            for division in iter(self.league[subleague].keys()):
                for team in self.league[subleague][division]:
                    if team.name == team_search.name:
                        return (subleague, division)
        return (None, None)

    def teams_in_league(self):
        teams = []
        for division in self.league.values():
            for teams_list in division.values():
                teams += teams_list
        return teams

    def team_names_in_league(self):
        teams = []
        for division in self.league.values():
            for teams_list in division.values():
                for team in teams_list:
                    teams.append(team.name)
        return teams

    def teams_in_subleague(self, subleague_name):
        teams = []
        if subleague_name in self.league.keys():
            for division_list in self.league[subleague_name].values():
                teams += division_list
            return teams
        else:
            print("League not found.")
            return None

    def teams_in_division(self, subleague_name, division_name):
        if subleague_name in self.league.keys() and division_name in self.league[subleague_name].keys():
            return self.league[subleague_name][division_name]
        else:
            print("Division in that league not found.")
            return None

    def make_matchups(self):
        matchups = []
        batch_subleagues = [] #each sub-array is all teams in each subleague
        subleague_max = 1
        league = deepcopy(self.league)
        for subleague in league.keys():
            teams = deepcopy(self.teams_in_subleague(subleague))
            if subleague_max < len(teams):
                subleague_max = len(teams)
            batch_subleagues.append(teams)

        for subleague in batch_subleagues:
            while len(subleague) < subleague_max:
                subleague.append("OFF")
   
        for i in range(0, self.constraints["inter_league_games"]): #generates inter-league matchups
            unmatched_indices = [i for i in range(0, len(batch_subleagues))]
            for subleague_index in range(0, len(batch_subleagues)):
                if subleague_index in unmatched_indices:
                    unmatched_indices.pop(unmatched_indices.index(subleague_index))
                    match_with_index = random.choice(unmatched_indices)
                    unmatched_indices.pop(unmatched_indices.index(match_with_index))
                    league_a = batch_subleagues[subleague_index].copy()
                    league_b = batch_subleagues[match_with_index].copy()
                    random.shuffle(league_a)
                    random.shuffle(league_b)
                    a_home = True
                    for team_a, team_b in zip(league_a, league_b):
                        if a_home:
                            matchups.append([team_b.name, team_a.name])
                        else:
                            matchups.append([team_a.name, team_b.name])
                        a_home = not a_home
                    
        for i in range(0, self.constraints["inter_div_games"]): #inter-division matchups
            extra_teams = []
            for subleague in league.keys():
                divisions = []
                for div in league[subleague].keys():
                    divisions.append(deepcopy(league[subleague][div]))

                #Check if there's an odd number of divisions
                last_div = None
                if len(divisions) % 2 != 0:
                    last_div = divisions.pop()

                #Get teams from half of the divisions
                divs_a = list(chain(divisions[int(len(divisions)/2):]))[0]
                if last_div is not None: #If there's an extra division, take half of those teams too
                    divs_a.extend(last_div[int(len(last_div)/2):])

                #Get teams from the other half of the divisions
                divs_b = list(chain(divisions[:int(len(divisions)/2)]))[0]
                if last_div is not None: #If there's an extra division, take the rest of those teams too
                    divs_b.extend(last_div[:int(len(last_div)/2)])

                #Ensure both groups have the same number of teams
                #Uness logic above changes, divs_a will always be one longer than divs_b or they'll be the same
                if len(divs_a) > len(divs_b):
                    divs_b.append(divs_a.pop())
    
                #Now we shuffle the groups
                random.shuffle(divs_a)
                random.shuffle(divs_b)
                
                #If there are an odd number of teams overall, then we need to remember the extra team for later
                if len(divs_a) < len(divs_b):
                    extra_teams.append(divs_b.pop())

                #Match up teams from each group
                a_home = True
                for team_a, team_b in zip(divs_a, divs_b):
                    if a_home:
                        matchups.append([team_b.name, team_a.name])
                    else:
                        matchups.append([team_a.name, team_b.name])
                    a_home = not a_home

            #Pair up any extra teams
            if extra_teams != []:
                if len(extra_teams) % 2 == 0:
                    for index in range(0, int(len(extra_teams)/2)):
                        matchups.append([extra_teams[index].name, extra_teams[index+1].name])
                        

        for subleague in league.keys():
            for division in league[subleague].values(): #generate round-robin matchups
                if len(division) % 2 != 0:
                    division.append("OFF")

                for i in range(0, len(division)-1):
                    teams_a = division[int(len(division)/2):]
                    teams_b = division[:int(len(division)/2)]
                    teams_b.reverse()

                    for team_a, team_b in zip(teams_a, teams_b):
                        if team_a != "OFF" and team_b != "OFF":
                            for j in range(0, self.constraints["division_games"]):                            
                                if i % 2 == 0:
                                    matchups.append([team_b.name, team_a.name])
                                else:
                                    matchups.append([team_a.name, team_b.name])

                            division.insert(1, division.pop())
        return matchups       
    
    def generate_schedule(self):
        matchups = self.make_matchups()
        random.shuffle(matchups)
        for game in matchups:
            scheduled = False      
            day = 1
            while not scheduled:
                found = False
                if str(day) in self.schedule.keys():
                    for game_on_day in self.schedule[str(day)]:
                        for team in game:
                            if team in game_on_day:
                                found = True
                    if not found:
                        self.schedule[str(day)].append(game)
                        scheduled = True
                else:
                    self.schedule[str(day)] = [game]
                    scheduled = True
                day += 1

        #now do forecasts
        for this_team in self.teams_in_league():
            start_weather = WeatherChains.starting_weather() #gets a random starting weather class
            start_weather_duration = random.randint(start_weather.duration_range[0], start_weather.duration_range[1])
            self.weather_forecast[this_team.name] = [start_weather.name] * start_weather_duration
            forecasted_days = []
            for i in range(start_weather_duration, len(self.schedule.keys()) * self.series_length):
                if i not in forecasted_days:
                    prev_weather = self.weather_forecast[this_team.name][i-1] #get last weather name
                    next_weather = WeatherChains.chain_weather(all_weathers()[prev_weather]) #ask weatherchains for next weather
                    next_weather_duration = random.randint(next_weather.duration_range[0], next_weather.duration_range[1])
                    self.weather_forecast[this_team.name] += [next_weather.name] * next_weather_duration
                    forecasted_days = [n for n in range(i, i + next_weather_duration)]

    def new_weathers_midseason(self, team_name): #generate new forecast for specific team
        start_weather = WeatherChains.starting_weather() #gets a random starting weather class
        start_weather_duration = self.day - 1 if self.day > 1 else random.randint(start_weather.duration_range[0], start_weather.duration_range[1])
        self.weather_forecast[team_name] = [start_weather.name] * start_weather_duration
        forecasted_days = []
        for i in range(start_weather_duration, len(self.schedule.keys()) * self.series_length):
            if i not in forecasted_days:
                prev_weather = self.weather_forecast[team_name][i-1] #get last weather name
                next_weather = WeatherChains.chain_weather(all_weathers()[prev_weather]) #ask weatherchains for next weather
                next_weather_duration = random.randint(next_weather.duration_range[0], next_weather.duration_range[1])
                self.weather_forecast[team_name] += [next_weather.name] * next_weather_duration
                forecasted_days = [n for n in range(i, i + next_weather_duration)]

    def division_standings(self, division, standings):
        def sorter(team_in_list):
            if team_in_list[2] == 0 and team_in_list[1] == 0:
                return (0, team_in_list[3])
            return (team_in_list[1]/(team_in_list[1]+team_in_list[2]), team_in_list[3])

        teams = division.copy()
        
        for index in range(0, len(teams)):
            this_team = teams[index]
            teams[index] = [this_team, standings[teams[index].name]["wins"], standings[teams[index].name]["losses"], standings[teams[index].name]["run_diff"], 0]

        teams.sort(key=sorter, reverse=True)
        return teams

    def past_standings(self, season_num):
        this_embed = Embed(color=Color.purple(), title=self.name)
        standings = {}
        for team_name, wins, losses, run_diff in league_db.get_past_standings(self.name, season_num):
            standings[team_name] = {"wins" : wins, "losses" : losses, "run_diff" : run_diff}

        this_embed.add_field(name=league_db.get_past_champion(self.name, season_num), value=f"Season {season_num} champions", inline = False)

        for subleague in iter(self.league.keys()):
            this_embed.add_field(name="Conference:", value=f"**{subleague}**", inline = False)
            for division in iter(self.league[subleague].keys()):
                teams = self.division_standings(self.league[subleague][division], standings)

                for index in range(0, len(teams)):
                    if index == self.constraints["division_leaders"] - 1:
                        teams[index][4] = "-"
                    else:
                        games_behind = ((teams[self.constraints["division_leaders"] - 1][1] - teams[index][1]) + (teams[index][2] - teams[self.constraints["division_leaders"] - 1][2]))/2
                        teams[index][4] = games_behind
                teams_string = ""
                for this_team in teams:
                    if this_team[2] != 0 or this_team[1] != 0:
                        teams_string += f"**{this_team[0].name}\n**{this_team[1]} - {this_team[2]} WR: {round(this_team[1]/(this_team[1]+this_team[2]), 3)} GB: {this_team[4]}\n\n"
                    else:
                        teams_string += f"**{this_team[0].name}\n**{this_team[1]} - {this_team[2]} WR: - GB: {this_team[4]}\n\n"

                this_embed.add_field(name=f"{division} Division:", value=teams_string, inline = False)
        
        this_embed.set_footer(text=f"Season {season_num} Final Standings")
        return this_embed

    def season_length(self):
        return int(list(self.schedule.keys())[-1]) * self.series_length
    
    def standings_embed(self):
        this_embed = Embed(color=Color.purple(), title=f"{self.name} Season {self.season}")
        standings = {}
        for team_name, wins, losses, run_diff in league_db.get_standings(self.name):
            standings[team_name] = {"wins" : wins, "losses" : losses, "run_diff" : run_diff}
        for subleague in iter(self.league.keys()):
            this_embed.add_field(name="Conference:", value=f"**{subleague}**", inline = False)
            for division in iter(self.league[subleague].keys()):
                teams = self.division_standings(self.league[subleague][division], standings)

                for index in range(0, len(teams)):
                    if index == self.constraints["division_leaders"] - 1:
                        teams[index][4] = "-"
                    else:
                        games_behind = ((teams[self.constraints["division_leaders"] - 1][1] - teams[index][1]) + (teams[index][2] - teams[self.constraints["division_leaders"] - 1][2]))/2
                        teams[index][4] = games_behind
                teams_string = ""
                for this_team in teams:
                    if this_team[2] != 0 or this_team[1] != 0:
                        teams_string += f"**{this_team[0].name}\n**{this_team[1]} - {this_team[2]} WR: {round(this_team[1]/(this_team[1]+this_team[2]), 3)} GB: {this_team[4]}\n\n"
                    else:
                        teams_string += f"**{this_team[0].name}\n**{this_team[1]} - {this_team[2]} WR: - GB: {this_team[4]}\n\n"

                this_embed.add_field(name=f"{division} Division:", value=teams_string, inline = False)
        
        this_embed.set_footer(text=f"Standings as of day {self.day-1} / {self.season_length()}")
        return this_embed

    def standings_embed_div(self, division, div_name):
        this_embed = Embed(color=Color.purple(), title=f"{self.name} Season {self.season}")
        standings = {}
        for team_name, wins, losses, run_diff in league_db.get_standings(self.name):
            standings[team_name] = {"wins" : wins, "losses" : losses, "run_diff" : run_diff}
        teams = self.division_standings(division, standings)

        for index in range(0, len(teams)):
            if index == self.constraints["division_leaders"] - 1:
                teams[index][4] = "-"
            else:
                games_behind = ((teams[self.constraints["division_leaders"] - 1][1] - teams[index][1]) + (teams[index][2] - teams[self.constraints["division_leaders"] - 1][2]))/2
                teams[index][4] = games_behind
        teams_string = ""
        for this_team in teams:
            if this_team[2] != 0 or this_team[1] != 0:
                teams_string += f"**{this_team[0].name}\n**{this_team[1]} - {this_team[2]} WR: {round(this_team[1]/(this_team[1]+this_team[2]), 3)} GB: {this_team[4]}\n\n"
            else:
                teams_string += f"**{this_team[0].name}\n**{this_team[1]} - {this_team[2]} WR: - GB: {this_team[4]}\n\n"

        this_embed.add_field(name=f"{div_name} Division:", value=teams_string, inline = False)
        this_embed.set_footer(text=f"Standings as of day {self.day-1} / {self.season_length()}")
        return this_embed

    def wildcard_embed(self):
        this_embed = Embed(color=Color.purple(), title=f"{self.name} Wildcard Race")
        standings = {}
        for team_name, wins, losses, run_diff in league_db.get_standings(self.name):
            standings[team_name] = {"wins" : wins, "losses" : losses, "run_diff" : run_diff}
        for subleague in iter(self.league.keys()):
            subleague_array = []
            for division in iter(self.league[subleague].keys()):
                this_div = [this_team for this_team, wins, losses, diff, gb in self.division_standings(self.league[subleague][division], standings)[self.constraints["division_leaders"]:]]
                subleague_array += this_div

            teams = self.division_standings(subleague_array, standings)
            teams_string = ""
            for index in range(0, len(teams)):
                if index == self.constraints["wild_cards"] - 1:
                    teams[index][4] = "-"
                else:
                    games_behind = ((teams[self.constraints["wild_cards"] - 1][1] - teams[index][1]) + (teams[index][2] - teams[self.constraints["wild_cards"] - 1][2]))/2
                    teams[index][4] = games_behind

            for this_team in teams:
                if this_team[2] != 0 or this_team[1] != 0:
                    teams_string += f"**{this_team[0].name}\n**{this_team[1]} - {this_team[2]} WR: {round(this_team[1]/(this_team[1]+this_team[2]), 3)} GB: {this_team[4]}\n\n"
                else:
                    teams_string += f"**{this_team[0].name}\n**{this_team[1]} - {this_team[2]} WR: - GB: {this_team[4]}\n\n"

            this_embed.add_field(name=f"{subleague} Conference:", value=teams_string, inline = False)
        
        this_embed.set_footer(text=f"Wildcard standings as of day {self.day-1}")
        return this_embed

    def champ_series(self):
        tournaments = []
        standings = {}
        
        for team_name, wins, losses, run_diff in league_db.get_standings(self.name):
            standings[team_name] = {"wins" : wins, "losses" : losses, "run_diff" : run_diff}

        for subleague in iter(self.league.keys()):
            team_dic = {}
            division_leaders = []
            subleague_array = []
            wildcard_leaders = []
            for division in iter(self.league[subleague].keys()):
                division_leaders += self.division_standings(self.league[subleague][division], standings)[:self.constraints["division_leaders"]]                
                this_div_wildcard = [this_team for this_team, wins, losses, diff, gb in self.division_standings(self.league[subleague][division], standings)[self.constraints["division_leaders"]:]]
                subleague_array += this_div_wildcard
            if self.constraints["wild_cards"] > 0:
                wildcard_leaders = self.division_standings(subleague_array, standings)[:self.constraints["wild_cards"]]

            for this_team, wins, losses, diff, gb in division_leaders + wildcard_leaders:
                team_dic[this_team] = {"wins" : wins}
            
            subleague_tournament = Tournament(f"{self.name} {subleague} Conference Series", team_dic, series_length=3, finals_series_length=5, secs_between_games=int(3600/self.games_per_hour), secs_between_rounds=int(7200/self.games_per_hour))
            subleague_tournament.build_bracket(by_wins = True)
            subleague_tournament.league = self
            tournaments.append(subleague_tournament)

        return tournaments

    def stat_embed(self, stat_name, season_num):
        if season_num is None:
            season_string = str(self.season)
            day = self.day
        else:
            season_string = str(season_num)
            day = len(self.schedule)
        this_embed = Embed(color=Color.purple(), title=f"{self.name} Season {season_string} {stat_name} Leaders")
        stats = league_db.get_stats(self.name, stat_name.lower(), day = day, season = season_num)        
        if stats is None:
            return None
        else:
            stat_names = list(stats[0].keys())[2:]
            for index in range(0, min(10,len(stats))):
                this_row = list(stats[index])
                player_name = this_row.pop(0)
                content_string = f"**{this_row.pop(0)}**\n"
                for stat_index in range(0, len(this_row)):
                    content_string += f"**{stat_names[stat_index]}**: {str(this_row[stat_index])}; "
                this_embed.add_field(name=player_name, value=content_string, inline=False)
            return this_embed

    def get_weather_now(self, team_name):
        if self.weather_override is None or self.weather_event_duration <= 0: #if no override set or if past event expired
            if self.day < len(self.weather_forecast[team_name]) and random.random() < 0.08: #8% chance the forcast was wrong
                if random.random() < 0.33:
                    return all_weathers()[self.weather_forecast[team_name][self.day]] #next weather came a day early
                elif random.random() < 0.66:
                    return random.choice(WeatherChains.parent_weathers(all_weathers()[self.weather_forecast[team_name][self.day]])) #pivot to different parent weather to lead in
                else:
                    return WeatherChains.chain_weather(all_weathers()[self.weather_forecast[team_name][self.day - 1]]) #jump to a child weather for a day
            return all_weathers()[self.weather_forecast[team_name][self.day - 1]]
        else:
            if self.weather_event_duration == 1 and random.random() < 0.1: #once per weather event, roll for forecast regen
                self.new_weathers_midseason(team_name)
            return self.weather_override

    def weather_event_check(self): #2 for new event, 1 for continued event, 0 for no event
        if self.day - self.last_weather_event_day > 20: #arbitrary cooldown between weather events
            if random.random() < 0.05: #5% chance for weather event?
                self.weather_override = all_weathers()["Supernova"]
                self.last_weather_event_day = self.day
                self.weather_event_duration = random.randint(self.weather_override.duration_range[0], self.weather_override.duration_range[1])
                return 2
        else:
            self.weather_event_duration -= 1
            return 1 if self.weather_event_duration > 0 else 0


class Tournament(object):
    def __init__(self, name, team_dic, series_length = 5, finals_series_length = 7, max_innings = 9, id = None, secs_between_games = 300, secs_between_rounds = 600): 
        self.name = name
        self.teams = team_dic #key: team object, value: wins
        self.bracket = None
        self.results = None
        self.series_length = series_length
        self.finals_length = finals_series_length
        self.game_length = max_innings
        self.active = False
        self.delay = secs_between_games
        self.round_delay = secs_between_rounds
        self.finals = False
        self.id = id
        self.league = None
        self.winner = None
        self.day = None

        if id is None:
            self.id = str(uuid4())
        else:
            self.id = id


    def build_bracket(self, random_sort = False, by_wins = False, manual = False):
        teams_list = list(self.teams.keys()).copy()

        if random_sort:
            def sorter(team_in_list):
                return random.random()

        elif by_wins:
            def sorter(team_in_list):
                return self.teams[team_in_list]["wins"] #sorts by wins

        else: #sort by average stars
            def sorter(team_in_list):
                return team_in_list.average_stars()
    
        if not manual:
            teams_list.sort(key=sorter, reverse=True)
        

        bracket_layers = int(math.ceil(math.log(len(teams_list), 2)))
        empty_slots = int(math.pow(2, bracket_layers) - len(teams_list))

        for i in range(0, empty_slots):
            teams_list.append(None)

        previous_bracket_layer = teams_list.copy()
        for i in range(0, bracket_layers - 1):
            this_layer = []
            for pair in range(0, int(len(previous_bracket_layer)/2)):
                if pair % 2 == 0: #if even number
                    this_layer.insert(0+int(pair/2), [previous_bracket_layer.pop(0), previous_bracket_layer.pop(-1)]) #every other pair goes at front of list, moving forward
                else:
                    this_layer.insert(0-int((1+pair)/2), [previous_bracket_layer.pop(int(len(previous_bracket_layer)/2)-1), previous_bracket_layer.pop(int(len(previous_bracket_layer)/2))]) #every other pair goes at end of list, moving backward
            previous_bracket_layer = this_layer
        self.bracket = Bracket(previous_bracket_layer, bracket_layers)

    def round_check(self):
        if self.bracket.depth == 1:
            self.finals = True
            return True
        else:
            return False

class Bracket(object):
    this_bracket = []

    def __init__(self, bracket_list, depth):
        self.this_bracket = bracket_list
        self.depth = depth
        self.bottom_row = []

    def get_bottom_row(self):
        self.depth = 1
        self.bottom_row = []
        self.dive(self.this_bracket)
        return self.bottom_row

    def dive(self, branch):
        if not isinstance(branch[0], list): #if it's a pair of games
            self.bottom_row.append(branch)
        else:
            self.depth += 1
            return self.dive(branch[0]), self.dive(branch[1])

    def set_winners_dive(self, winners_list, index = 0, branch = None, parent = None):
        if branch is None:
            branch = self.this_bracket.copy()
        if not isinstance(branch[0], list): #if it's a pair of games
            if branch[0].name in winners_list or branch[1] is None:
                winner = branch[0]
                if parent is not None:
                    parent[index] = winner
            elif branch[1].name in winners_list:
                winner = branch[1]
                if parent is not None:
                    parent[index] = winner        
        else:
            self.set_winners_dive(winners_list, index = 0, branch = branch[0], parent = branch)
            self.set_winners_dive(winners_list, index = 1, branch = branch[1], parent = branch)

        if parent is None:
            self.this_bracket = branch
            return branch

def save_league(this_league):
    if not league_db.league_exists(this_league.name):
        league_db.init_league_db(this_league)
        with open(os.path.join(data_dir, league_dir, this_league.name, f"{this_league.name}.league"), "w") as league_file:
            league_json_string = jsonpickle.encode(this_league.league, keys=True)
            json.dump(league_json_string, league_file, indent=4)
    league_db.save_league(this_league)

def save_league_as_new(this_league):
    league_db.init_league_db(this_league)
    with open(os.path.join(data_dir, league_dir, this_league.name, f"{this_league.name}.league"), "w") as league_file:
        league_json_string = jsonpickle.encode(this_league.league, keys=True)
        json.dump(league_json_string, league_file, indent=4)
    league_db.save_league(this_league)

def load_league_file(league_name):
    if league_db.league_exists(league_name):
        state = league_db.state(league_name)
        this_league = League(league_name)
        with open(os.path.join(data_dir, league_dir, league_name, f"{this_league.name}.league")) as league_file:
            this_league.league = jsonpickle.decode(json.load(league_file), keys=True, classes=team)
        with open(os.path.join(data_dir, league_dir, league_name, f"{this_league.name}.state")) as state_file:
            state_dic = json.load(state_file)

        this_league.day = state_dic["day"]
        this_league.schedule = state_dic["schedule"]
        this_league.constraints = state_dic["constraints"]
        this_league.game_length = state_dic["game_length"]
        this_league.series_length = state_dic["series_length"]
        this_league.owner = state_dic["owner"]
        this_league.games_per_hour = state_dic["games_per_hour"]
        this_league.historic = state_dic["historic"]
        this_league.season = state_dic["season"]
        try:
            this_league.champion = state_dic["champion"]
        except:
            this_league.champion = None
        try: 
            this_league.weather_forecast = state_dic["forecasts"] #handles legacy leagues
        except: 
            this_league.weather_forecast = {}
            for this_team in this_league.teams_in_league(): #give them all fresh forecasts starting at current day
                this_league.new_weathers_midseason(this_team.name)
            save_league(this_league)
        try:
            this_league.last_weather_event_day = state_dic["last_weather_event"]
        except:
            this_league.last_weather_event_day = 0
        try:
            this_league.subbed_channels = state_dic["subs"]
        except:
            this_league.subbed_channels = []
        return this_league


async def league_day_watcher(channel, league, games_list, filter_url, last = False, missed = 0):
    league.active = True
    league.autoplay -= 1
    if league not in active_leagues:
        active_leagues.append(league)
    series_results = {}

    while league.active:
        queued_games = []
        while len(games_list) > 0:
            try:
                for i in range(0, len(games_list)):
                    game, key = games_list[i]
                    if game.over: # and ((key in main_controller.master_games_dic.keys() and main_controller.master_games_dic[key][1]["end_delay"] <= 8) or not key in main_controller.master_games_dic.keys()):
                        if game.teams['home'].name not in series_results.keys():
                            series_results[game.teams["home"].name] = {}
                            series_results[game.teams["home"].name]["wins"] = 0
                            series_results[game.teams["home"].name]["losses"] = 0
                            series_results[game.teams["home"].name]["run_diff"] = 0
                        if game.teams['away'].name not in series_results.keys():
                            series_results[game.teams["away"].name] = {}
                            series_results[game.teams["away"].name]["wins"] = 0
                            series_results[game.teams["away"].name]["losses"] = 0
                            series_results[game.teams["away"].name]["run_diff"] = 0

                        winner_name = game.teams['home'].name if game.teams['home'].score > game.teams['away'].score else game.teams['away'].name
                        loser_name = game.teams['away'].name if game.teams['home'].score > game.teams['away'].score else game.teams['home'].name
                        rd = int(math.fabs(game.teams['home'].score - game.teams['away'].score))

                        series_results[winner_name]["wins"] += 1
                        series_results[winner_name]["run_diff"] += rd

                        winner_dic = {"wins" : 1, "run_diff" : rd}

                        series_results[loser_name]["losses"] += 1
                        series_results[loser_name]["run_diff"] -= rd

                        loser_dic = {"losses" : 1, "run_diff" : -rd}

                        league.add_stats_from_game(game.get_team_specific_stats())
                        league.update_standings({winner_name : winner_dic, loser_name : loser_dic})
                        league.save_league(league)
                        final_embed = game_over_embed(game)
                        final_embed.add_field(name="Day:", value=league.day)
                        final_embed.add_field(name="Series score:", value=f"{series_results[game.teams['away'].name]['wins']} - {series_results[game.teams['home'].name]['wins']}")
                        await league_subscriber_update(league, channel, f"A {league.name} game just ended!")                
                        await league_subscriber_update(league, channel, final_embed)
                        if series_results[winner_name]["wins"] + series_results[winner_name]["losses"] + missed < league.series_length:
                            queued_games.append(game)                           
                        games_list.pop(i)
                        break
            except:
                print("something went wrong in league_day_watcher: " + str(sys.exc_info()[0]) + str(sys.exc_info()[1]) + "\n" + traceback.print_tb(sys.exc_info()[2]))
            await asyncio.sleep(2)
        league.day += 1
        
        if len(queued_games) > 0:

            now = datetime.datetime.now()

            validminutes = [0] + [int((60 * div)/league.games_per_hour) for div in range(1,league.games_per_hour)]

            delta = datetime.timedelta()

            for i in range(0, len(validminutes)):
                if now.minute > validminutes[i]:
                    if i <= len(validminutes)-3:
                        if validminutes[i+1] == now.minute:
                            delta = datetime.timedelta(minutes= (validminutes[i+2] - now.minute))
                        else:
                            delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                    elif i <= len(validminutes)-2:
                        if validminutes[i+1] == now.minute:
                            delta = datetime.timedelta(minutes= (60 - now.minute))
                        else:
                            delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                    else:
                        delta = datetime.timedelta(minutes= (60 - now.minute))           

            next_start = (now + delta).replace(second=0, microsecond=0)
            wait_seconds = (next_start - now).seconds

            if wait_seconds > 3600: #there's never a situation to wait longer than an hour so hoo ray bugfixes the easy way
                wait_seconds = 60
                
            league.save_league(league)
            active_standings[league] = await channel.send(embed=league.standings_embed())
            await league_subscriber_update(league, channel, f"The day {league.day} games for the {league.name} will start in {math.ceil(wait_seconds/60)} minutes.")
            weather_check_result = league.weather_event_check()
            if weather_check_result == 2:
                await league_subscriber_update(league, channel, f"The entire league is struck by a {league.weather_override.emoji} {league.weather_override.name}! The games must go on.")
            elif weather_check_result == 1:
                await league_subscriber_update(league, channel, f"The {league.weather_override.emoji} {league.weather_override.name} continues to afflict the league.")
            await asyncio.sleep(wait_seconds)
            await league_subscriber_update(league, channel, f"A {league.name} series is continuing now at {filter_url}")
            games_list = await continue_league_series(league, queued_games, games_list, series_results, missed)
        else:
            league.active = False

    if league.autoplay == 0 or config()["game_freeze"]: #if number of series to autoplay has been reached
        active_standings[league] = await league_subscriber_update(league, channel, league.standings_embed())
        await league_subscriber_update(league, channel, f"The {league.name} is no longer autoplaying.")
        if config()["game_freeze"]:
            await channel.send("Patch incoming.")
        league.save_league(league)
        active_leagues.pop(active_leagues.index(league))
        return

    if last: #if last game of the season
        now = datetime.datetime.now()
        validminutes = [int((60 * div)/league.games_per_hour) for div in range(0,league.games_per_hour)]
        delta = datetime.timedelta()
        for i in range(0, len(validminutes)):
            if now.minute > validminutes[i]:
                if i <= len(validminutes)-3:
                    if validminutes[i+1] == now.minute:
                        delta = datetime.timedelta(minutes= (validminutes[i+2] - now.minute))
                    else:
                        delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                elif i <= len(validminutes)-2:
                    if validminutes[i+1] == now.minute:
                        delta = datetime.timedelta(minutes= (60 - now.minute))
                    else:
                        delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                else:
                    delta = datetime.timedelta(minutes= (60 - now.minute))           

        next_start = (now + delta).replace(second=0, microsecond=0)
        wait_seconds = (next_start - now).seconds
        await league_subscriber_update(league, channel, f"This {league.name} season is now over! The postseason (with any necessary tiebreakers) will be starting in {math.ceil(wait_seconds/60)} minutes. (unless you skipped it, that is.)")
        await asyncio.sleep(wait_seconds)
        await league_postseason(channel, league)

        #need to reset league to new season here

        return





    

    now = datetime.datetime.now()

    validminutes = [int((60 * div)/league.games_per_hour) for div in range(0,league.games_per_hour)]
    delta = datetime.timedelta()
    for i in range(0, len(validminutes)):
        if now.minute > validminutes[i]:
            if i <= len(validminutes)-3:
                if validminutes[i+1] == now.minute:
                    delta = datetime.timedelta(minutes= (validminutes[i+2] - now.minute))
                else:
                    delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
            elif i <= len(validminutes)-2:
                if validminutes[i+1] == now.minute:
                    delta = datetime.timedelta(minutes= (60 - now.minute))
                else:
                    delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
            else:
                delta = datetime.timedelta(minutes= (60 - now.minute))           

    next_start = (now + delta).replace(second=0, microsecond=0)
    wait_seconds = (next_start - now).seconds

    league.save_league(league)
    active_standings[league] = await league_subscriber_update(league, channel, league.standings_embed())
    await league_subscriber_update(league, channel, f"""This {league.name} series is now complete! The next series will be starting in {int(wait_seconds/60)} minutes.""")
    await asyncio.sleep(wait_seconds)

    await start_league_day(channel, league)

async def continue_league_series(league, queue, games_list, series_results, missed):
    for oldgame in queue:
        away_team = game.get_team(oldgame.teams["away"].name)
        away_team.set_pitcher(rotation_slot=league.day)
        home_team = game.get_team(oldgame.teams["home"].name)
        home_team.set_pitcher(rotation_slot=league.day)
        this_game = game.game(away_team.finalize(), home_team.finalize(), length = league.game_length)
        this_game.weather = league.get_weather_now(home_team.name)(this_game)
        this_game, state_init = prepare_game(this_game, league=league)

        series_string = f"Series score:"

        if missed <= 0:
            series_string = "Series score:"
            state_init["title"] = f"{series_string} {series_results[away_team.name]['wins']} - {series_results[home_team.name]['wins']}"
        else:
            state_init["title"] = "Interrupted series!"
        discrim_string = league.name

        id = str(uuid4())
        games_list.append((this_game, id))
        # main_controller.master_games_dic[id] = (this_game, state_init, discrim_string)

    return games_list

async def league_postseason(channel, league):
    embed = league.standings_embed()
    embed.set_footer(text="Final Standings")
    await channel.send(embed=embed)
        
    if league.postseason:

        tiebreakers = league.tiebreaker_required()       
        if tiebreakers != []:
            await channel.send("Tiebreakers required!")
            await asyncio.gather(*[start_tournament_round(channel, tourney) for tourney in tiebreakers])
            for tourney in tiebreakers:
                league.update_standings({tourney.winner.name : {"wins" : 1}})
                league.save_league(league)
            now = datetime.datetime.now()

            validminutes = [int((60 * div)/league.games_per_hour) for div in range(0,league.games_per_hour)]
            delta = datetime.timedelta()
            for i in range(0, len(validminutes)):
                if now.minute > validminutes[i]:
                    if i <= len(validminutes)-3:
                        if validminutes[i+1] == now.minute:
                            delta = datetime.timedelta(minutes= (validminutes[i+2] - now.minute))
                        else:
                            delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                    elif i <= len(validminutes)-2:
                        if validminutes[i+1] == now.minute:
                            delta = datetime.timedelta(minutes= (60 - now.minute))
                        else:
                            delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                    else:
                        delta = datetime.timedelta(minutes= (60 - now.minute))           

            next_start = (now + delta).replace(second=0, microsecond=0)
            wait_seconds = (next_start - now).seconds
            await league_subscriber_update(league, channel, f"Tiebreakers complete! Postseason starting in {math.ceil(wait_seconds/60)} minutes.")
            await asyncio.sleep(wait_seconds)
            

        tourneys = league.champ_series()
        await asyncio.gather(*[start_tournament_round(channel, tourney) for tourney in tourneys])
        champs = {}
        for tourney in tourneys:
            for team in tourney.teams.keys():
                if team.name == tourney.winner.name:
                    champs[tourney.winner] = {"wins" : tourney.teams[team]["wins"]}
        world_series = league.Tournament(f"{league.name} Championship Series", champs, series_length=7, secs_between_games=int(3600/league.games_per_hour), secs_between_rounds=int(7200/league.games_per_hour))
        world_series.build_bracket(by_wins = True)
        world_series.league = league
        now = datetime.datetime.now()

        validminutes = [int((60 * div)/league.games_per_hour) for div in range(0,league.games_per_hour)]
        delta = datetime.timedelta()
        for i in range(0, len(validminutes)):
            if now.minute > validminutes[i]:
                if i <= len(validminutes)-3:
                    if validminutes[i+1] == now.minute:
                        delta = datetime.timedelta(minutes= (validminutes[i+2] - now.minute))
                    else:
                        delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                elif i <= len(validminutes)-2:
                    if validminutes[i+1] == now.minute:
                        delta = datetime.timedelta(minutes= (60 - now.minute))
                    else:
                        delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                else:
                    delta = datetime.timedelta(minutes= (60 - now.minute))           

        next_start = (now + delta).replace(second=0, microsecond=0)
        wait_seconds = (next_start - now).seconds
        await league_subscriber_update(league, channel, f"The {league.name} Championship Series is starting in {math.ceil(wait_seconds/60)} minutes!")
        await asyncio.sleep(wait_seconds)
        await start_tournament_round(channel, world_series)
        league.champion = world_series.winner.name

    league.save_league(league)
    season_save(league)
    league.season_reset()

async def league_subscriber_update(league, start_channel, message):
    channel_list = list(filter(lambda chan : chan.id in league.subbed_channels, client.get_all_channels()))
    channel_list.append(start_channel)
    for channel in channel_list:
        if isinstance(message, discord.Embed):
            await channel.send(embed=message)
        else:
            await channel.send(message)


async def start_league_day(channel, league, partial = False):
    current_games = []
        
    games_to_start = league.schedule[str(league.day_to_series_num(league.day))]
    if league.game_length is None:
        game_length = game.config()["default_length"]
    else:
        game_length = league.game_length

    weather_check_result = league.weather_event_check()

    for pair in games_to_start:
        if pair[0] is not None and pair[1] is not None:
            away = get_team_fuzzy_search(pair[0])
            away.set_pitcher(rotation_slot=league.day)
            home = get_team_fuzzy_search(pair[1])
            home.set_pitcher(rotation_slot=league.day)

            this_game = game.game(away.finalize(), home.finalize(), length = game_length)
            this_game.weather = league.get_weather_now(home.name)(this_game)
            this_game, state_init = prepare_game(this_game, league=league)

            if not partial:
                series_string = "Series score:"
                state_init["title"] = f"{series_string} 0 - 0"
            else:
                state_init["title"] = "Interrupted series!"
            discrim_string = league.name     

            id = str(uuid4())
            current_games.append((this_game, id))
            # main_controller.master_games_dic[id] = (this_game, state_init, discrim_string)

    ext = "?league=" + urllib.parse.quote_plus(league.name)
    
    if weather_check_result == 2:
        await league_subscriber_update(league, channel, f"The entire league is struck by a {league.weather_override.emoji} {league.weather_override.name}! The games must go on.")
    elif weather_check_result == 1:
        await league_subscriber_update(league, channel, f"The {league.weather_override.emoji} {league.weather_override.name} continues to afflict the league.")

    if league.last_series_check(): #if finals
        await league_subscriber_update(league, channel, f"The final series of the {league.name} regular season is starting now, at {config()['simmadome_url']+ext}")
        last = True

    else:
        await league_subscriber_update(league, channel, f"The day {league.day} series of the {league.name} is starting now, at {config()['simmadome_url']+ext}")
        last = False

    if partial:
        missed_games = (league.day % league.series_length) - 1
        if missed_games == -1:
            missed_games = league.series_length - 1
        await league_day_watcher(channel, league, current_games, config()['simmadome_url']+ext, last, missed = missed_games)
    else:
        await league_day_watcher(channel, league, current_games, config()['simmadome_url']+ext, last)


async def tourney_round_watcher(channel, tourney, games_list, filter_url, finals = False):
    tourney.active = True
    active_tournaments.append(tourney)
    wins_in_series = {}
    winner_list = []
    while tourney.active:
        queued_games = []
        while len(games_list) > 0:
            try:
                for i in range(0, len(games_list)):
                    game, key = games_list[i]
                    if game.over: # and ((key in main_controller.master_games_dic.keys() and main_controller.master_games_dic[key][1]["end_delay"] <= 8) or not key in main_controller.master_games_dic.keys()):
                        if game.teams['home'].name not in wins_in_series.keys():
                            wins_in_series[game.teams["home"].name] = 0
                        if game.teams['away'].name not in wins_in_series.keys():
                            wins_in_series[game.teams["away"].name] = 0

                        winner_name = game.teams['home'].name if game.teams['home'].score > game.teams['away'].score else game.teams['away'].name

                        if winner_name in wins_in_series.keys():
                            wins_in_series[winner_name] += 1
                        else:
                            wins_in_series[winner_name] = 1

                        final_embed = game_over_embed(game)
                        final_embed.add_field(name="Series score:", value=f"{wins_in_series[game.teams['away'].name]} - {wins_in_series[game.teams['home'].name]}")
                        if tourney.league is not None:
                            await league_subscriber_update(tourney.league, channel, f"A {tourney.name} game just ended!")
                            await league_subscriber_update(tourney.league, channel, final_embed)
                        else:
                            await channel.send(f"A {tourney.name} game just ended!")                
                            await channel.send(embed=final_embed)
                        if wins_in_series[winner_name] >= int((tourney.series_length+1)/2) and not finals:
                            winner_list.append(winner_name)
                        elif wins_in_series[winner_name] >= int((tourney.finals_length+1)/2):
                            winner_list.append(winner_name)
                        else:
                            queued_games.append(game)
                            
                        games_list.pop(i)
                        break
            except:
                print("something went wrong in tourney_watcher")
            await asyncio.sleep(4)
        if tourney.league is not None:
            tourney.day += 1
        
        if len(queued_games) > 0:
            
            if tourney.league is not None:
                now = datetime.datetime.now()
                validminutes = [int((60 * div)/tourney.league.games_per_hour) for div in range(0,tourney.league.games_per_hour)]
                for i in range(0, len(validminutes)):
                    if now.minute > validminutes[i]:
                        if i <= len(validminutes)-3:
                            if validminutes[i+1] == now.minute:
                                delta = datetime.timedelta(minutes= (validminutes[i+2] - now.minute))
                            else:
                                delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                        elif i <= len(validminutes)-2:
                            if validminutes[i+1] == now.minute:
                                delta = datetime.timedelta(minutes= (60 - now.minute))
                            else:
                                delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                        else:
                            delta = datetime.timedelta(minutes= (60 - now.minute))           

                next_start = (now + delta).replace(second=0, microsecond=0)
                wait_seconds = (next_start - now).seconds               
                if tourney.league is not None:
                    await league_subscriber_update(tourney.league, channel, f"The next batch of games for the {tourney.name} will start in {math.ceil(wait_seconds/60)} minutes.")
                else:
                    await channel.send(f"The next batch of games for the {tourney.name} will start in {math.ceil(wait_seconds/60)} minutes.")
                await asyncio.sleep(wait_seconds)
            else:
                if tourney.league is not None:
                    await league_subscriber_update(tourney.league, channel, f"The next batch of games for {tourney.name} will start in {int(tourney.delay/60)} minutes.")
                else:
                    await channel.send(f"The next batch of games for {tourney.name} will start in {int(tourney.delay/60)} minutes.")
                await asyncio.sleep(tourney.delay)
            if tourney.league is not None:
                await league_subscriber_update(tourney.league, channel, f"{len(queued_games)} games for {tourney.name}, starting at {filter_url}")
            else:
                await channel.send(f"{len(queued_games)} games for {tourney.name}, starting at {filter_url}")
            games_list = await continue_tournament_series(tourney, queued_games, games_list, wins_in_series)
        else:
            tourney.active = False

    if finals: #if this last round was finals
        embed = discord.Embed(color = discord.Color.dark_purple(), title = f"{winner_list[0]} win the {tourney.name} finals!")
        if tourney.league is not None and tourney.day > tourney.league.day:
            tourney.league.day = tourney.day
        if tourney.league is not None:
            await league_subscriber_update(tourney.league, channel, embed)
        else:
            await channel.send(embed=embed)
        tourney.winner = get_team_fuzzy_search(winner_list[0])
        active_tournaments.pop(active_tournaments.index(tourney))
        return

    tourney.bracket.set_winners_dive(winner_list)

    winners_string = ""
    for game in tourney.bracket.get_bottom_row():
        winners_string += f"{game[0].name}\n{game[1].name}\n"

    if tourney.league is not None:
        now = datetime.datetime.now()
        validminutes = [int((60 * div)/tourney.league.games_per_hour) for div in range(0,tourney.league.games_per_hour)]
        for i in range(0, len(validminutes)):
            if now.minute > validminutes[i]:
                if i <= len(validminutes)-3:
                    if validminutes[i+1] == now.minute:
                        delta = datetime.timedelta(minutes= (validminutes[i+2] - now.minute))
                    else:
                        delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                elif i <= len(validminutes)-2:
                    if validminutes[i+1] == now.minute:
                        delta = datetime.timedelta(minutes= (60 - now.minute))
                    else:
                        delta = datetime.timedelta(minutes= (validminutes[i+1] - now.minute))
                else:
                    delta = datetime.timedelta(minutes= (60 - now.minute))           

        next_start = (now + delta).replace(second=0, microsecond=0)
        wait_seconds = (next_start - now).seconds
        await league_subscriber_update(tourney.league, channel, f"""This round of games for the {tourney.name} is now complete! The next round will start in {math.ceil(wait_seconds/60)} minutes.
Advancing teams:
{winners_string}""")
        await asyncio.sleep(wait_seconds)
    else:
        await channel.send(f"""
This round of games for {tourney.name} is now complete! The next round will be starting in {int(tourney.round_delay/60)} minutes.
Advancing teams:
{winners_string}""")
        await asyncio.sleep(tourney.round_delay)
    await start_tournament_round(channel, tourney)


async def start_tournament_round(channel, tourney, seeding = None):
    current_games = []
    if tourney.bracket is None:
        if seeding is None:
            tourney.build_bracket(random_sort=True)

    games_to_start = tourney.bracket.get_bottom_row()

    for pair in games_to_start:
        if pair[0] is not None and pair[1] is not None:
            team_a = get_team_fuzzy_search(pair[0].name)
            team_b = get_team_fuzzy_search(pair[1].name)

            if tourney.league is not None:
                if tourney.day is None:
                    tourney.day = tourney.league.day
                team_a.set_pitcher(rotation_slot = tourney.day)
                team_b.set_pitcher(rotation_slot = tourney.day)

            this_game = game.game(team_a.finalize(), team_b.finalize(), length = tourney.game_length)
            this_game, state_init = prepare_game(this_game)

            state_init["is_league"] = True

            if tourney.round_check():
                series_string = f"Best of {tourney.finals_length}:"
            else:
                series_string = f"Best of {tourney.series_length}:"
            state_init["title"] = f"{series_string} 0 - 0"
            discrim_string = tourney.name     

            id = str(uuid4())
            current_games.append((this_game, id))
            # main_controller.master_games_dic[id] = (this_game, state_init, discrim_string)

    ext = "?league=" + urllib.parse.quote_plus(tourney.name)

    if tourney.round_check(): #if finals        
        if tourney.league is not None:
            await league_subscriber_update(tourney.league, channel, f"The {tourney.name} finals are starting now, at {config()['simmadome_url']+ext}")
        else:
            await channel.send(f"The {tourney.name} finals are starting now, at {config()['simmadome_url']+ext}")
        finals = True

    else:  
        if tourney.league is not None:
            await league_subscriber_update(tourney.league, channel, f"{len(current_games)} games started for the {tourney.name} tournament, at {config()['simmadome_url']+ext}")
        else:
            await channel.send(f"{len(current_games)} games started for the {tourney.name} tournament, at {config()['simmadome_url']+ext}")
        finals = False
    await tourney_round_watcher(channel, tourney, current_games, config()['simmadome_url']+ext, finals)

async def continue_tournament_series(tourney, queue, games_list, wins_in_series):
    for oldgame in queue:
        away_team = game.get_team(oldgame.teams["home"].name)
        home_team = game.get_team(oldgame.teams["away"].name)

        if tourney.league is not None:
            if tourney.day is None:
                tourney.day = tourney.league.day
            away_team.set_pitcher(rotation_slot = tourney.day)
            home_team.set_pitcher(rotation_slot = tourney.day)
            

        this_game = game.game(away_team.finalize(), home_team.finalize(), length = tourney.game_length)
        this_game, state_init = prepare_game(this_game)

        state_init["is_league"] = True

        if tourney.round_check():
            series_string = f"Best of {tourney.finals_length}:"
        else:
            series_string = f"Best of {tourney.series_length}:"

        state_init["title"] = f"{series_string} {wins_in_series[away_team.name]} - {wins_in_series[home_team.name]}"

        discrim_string = tourney.name     

        id = str(uuid4())
        games_list.append((this_game, id))
        # main_controller.master_games_dic[id] = (this_game, state_init, discrim_string)

    return games_list

@app.route('/api/leagues', methods=['POST'])
def create_league():
    config = json.loads(request.data)

    if league_exists(config['name']):
        return jsonify({'status':'err_league_exists'}), 400

    num_subleagues = len(config['structure']['subleagues'])
    if num_subleagues < 1:
        return jsonify({'status':'err_invalid_subleague_count'}), 400

    num_divisions = len(config['structure']['subleagues'][0]['divisions'])
    if num_subleagues * (num_divisions + 1) > MAX_SUBLEAGUE_DIVISION_TOTAL:
        return jsonify({'status':'err_invalid_subleague_division_total'}), 400

    league_dic = {}
    all_teams = set()
    err_teams = []
    for subleague in config['structure']['subleagues']:
        if subleague['name'] in league_dic:
            return jsonify({'status':'err_duplicate_name', 'cause':subleague['name']})

        subleague_dic = {}
        for division in subleague['divisions']:
            if division['name'] in subleague_dic:
                return jsonify({'status':'err_duplicate_name', 'cause':f"{subleague['name']}/{division['name']}"}), 400
            elif len(division['teams']) > MAX_TEAMS_PER_DIVISION:
                return jsonify({'status':'err_too_many_teams', 'cause':f"{subleague['name']}/{division['name']}"}), 400

            teams = []
            for team_name in division['teams']:
                if team_name in all_teams:
                    return jsonify({'status':'err_duplicate_team', 'cause':team_name}), 400
                all_teams.add(team_name)
                
                team = game.get_team(team_name)
                if team is None:
                    err_teams.append(team_name)
                else:
                    teams.append(team)
            subleague_dic[division['name']] = teams
        league_dic[subleague['name']] = subleague_dic

    if len(err_teams) > 0:
        return jsonify({'status':'err_no_such_team', 'cause': err_teams}), 400

    for (key, min_val) in [
        ('division_series', 1), 
        ('inter_division_series', 0), 
        ('inter_league_series', 0)
    ]:
        if config[key] < min_val:
            return jsonify({'status':'err_invalid_option_value', 'cause':key}), 400

    new_league = League(config['name'])
    new_league.setup(
        league_dic, 
        division_games=config['division_series'],
        inter_division_games=config['inter_division_series'],
        inter_league_games=config['inter_league_series'],
    )
    new_league.constraints["division_leaders"] = config["top_postseason"]
    new_league.constraints["wild_cards"] = config["wildcards"]
    new_league.generate_schedule()
    league.save_league(new_league)

    return jsonify({'status':'success_league_created'})