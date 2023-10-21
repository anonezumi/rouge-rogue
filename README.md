# rouge-rogue
# Rouge Rogue discord bot: baseball simulation

Rouge Rogue is a discord based online baseball simulator inspired by Blaseball and based on [Sim16](https://github.com/Sakimori/matteo-the-prestige), every name has randomly generated stats which you can use to make custom teams and custom leagues, all set up and run in Discord!

If you would like to add the bot to your server to be able to set up teams and games, [click here](https://discord.com/oauth2/authorize?client_id=1094647888279244871&scope=bot&permissions=26845492071504).

If you would like to chat with the devs or join the main community for the bot that can all be found in [the Discord server](https://discord.gg/hYWExS6f8D).

Discord is also the ideal place for suggestions, bug reports, and questions about the bot.

## Commands:
### Team Commands:
#### Creation and Deletion:
- /saveteam: Saves a team to the database allowing it to be used for games. Pitchers and batters must be separated by commas. If you did it correctly, you'll get a team embed with a prompt to confirm. hit the 👍 and your team will be saved!
- /deleteteam: Allows you to delete the team with the provided name. You'll get an embed with a confirmation to prevent accidental deletions. Hit the 👍 and your team will be deleted.
#### Editing (all of these commands require ownership and exact spelling of the team name):
- /replaceplayer: Replaces a player on your team with a new player. if there are multiple copies of the same player on a team this will only replace the first one.
- /addplayer: Adds a new player to the end of your team's lineup or the rotation.
- /moveplayer: Moves a player within your lineup or rotation. If you want to instead move a player from your rotation to your lineup or vice versa, use /swapsection instead.
- /swapsection: Swaps a player from your lineup to the end of your rotation or your rotation to the end of your lineup.
- /removeplayer: Removes a player from your team. if there are multiple copies of the same player on a team this will only delete the first one.
#### Viewing and Searching:
- /showteam: Shows the lineup, rotation, and slogan of any saved team in a discord embed with primary stat star ratings for all of the players. This command has fuzzy search so you don't need to type the full name of the team as long as you give enough to identify the team you're looking for.
- /searchteams: Shows a paginated list of all teams whose names contain the given search term.
- /showallteams: Shows a paginated list of all teams available for games which can be scrolled through.

### Game Commands:
#### Individual Game Commands:
- /startgame: Starts a game with premade teams made using saveteam. You can optionally set the day (offset for the rotation), weather, and commentator.
- /randomgame: Starts a game between 2 entirely random teams. Embrace chaos!
#### Tournament Commands:
- /starttournament: Starts a randomly seeded tournament with the provided teams, automatically adding byes as necessary. All series have a 5 minute break between games. The default format is teams seeded randomly best of 5 until the finals which are best of 7.
#### Draft Commands
- /startdraft: Starts a draft with an arbitrary number of participants. By default teams will draft in order from a pool of 20 players until there are 5 left at which point the pool will refresh. By default each team will select 13 players, 12 hitters and 1 pitcher in that order, but all of these numbers can be modified via optional arguments. The draft will begin once all participants have given a 👍 and will proceed in the order that participants were entered.
- /draft: Use this on your turn during a draft to pick your player.
#### League Commissioner Commands
- /addleagueowner: Give the specified user owner powers in your league.
- /startleague: Starts the playing of league games at the pace specified, by default will play the entire season and the postseason unless an owner pauses the league with the /pauseleague command. 
- /pauseleague: Pauses the specified league after the current series finishes until the league is started again with /startleague.
- /leagueseasonreset: Completely scraps the given league's current season, resetting everything to day 1 of the current season. Make sure to use /startleague again to restart the season afterwards.
- /leaguereplaceteam: Replaces a team in a league with a new team. Can only be done in the offseason.
- /swapteams: Swaps the division/conference of two teams in a league.
#### League Commands
- /leaguestandings: Displays the current standings for the specified league. By default this will display the standings for the current season, but you can also display historical standings by specifying a season.
- /leaguewildcard: Displays the wild card standings for the specified league. If the league doesn't have wild cards, it will instead tell you that.
- /leagueschedule: Displays the upcoming schedule for the specified league including the weather forecast. Shows the current series and the next three series after that for every team.
- /teamchedule: Displays the upcoming schedule for the specified team within the specified league including the weather forecast. Shows the current series and the next six series after that for the given team.
- /leagueleaders: Displays a league's leaders in the given stat.
  - The currently available stats are:
    - For batters: avg (batting average), slg (slugging percentage), obp (on-base percentage), ops (on-base plus slugging), home runs, walks drawn. 
    - For pitchers era (earned run average), whip (walks and hits per innings pitched), kper9 (strikeouts per 9 innings), bbper9 (walks per 9 innings), kperbb (strikeout to walk ratio), eramin (players with the worst earned run average). 
- /leaguesub: Posts all league feed events to this channel, in addition to the channel the league was started in. Run again to unsubscribe.

### Player Commands:	 
- /showplayer: Displays any name's stars, there's a limit of 70 characters which is the max which can be used on a team.
- /idolize: Records any name as your idol, mostly for fun.
- /showidol: Displays your idol's name and stars in a discord embed.
  
### Other Commands:
- /help: Shows instructions for a given command. If no command is provided, it will instead provide a list of all of the commands that instructions can be provided for.

## Weathers
- All current weathers are listed here with a short description of their effects except for the most recent weathers whose effects remain a mystery.
  - Supernova 🌟: Makes all pitchers pitch worse, significantly increased effect on stronger pitchers.
  - Midnight 🕶: Significantly increased the chance that players will attempt to steal a base.
  - Blizzard ❄: Occasionally causes the team's pitcher to bat in place of the scheduled batter.
  - Slight Tailwind 🏌️‍♀: Occasionally batters get a mulligan and start the at bat over if they would have gotten out, significantly more likely to happen for weaker batters. 
  - Thinned Veil 🌌: When a player hits a dinger, they end up on the base corresponding to the number of runs the dinger scored, 1st base if it's a solo home run, up to none base if it's a grand slam, resulting in 5 runs scoring.
  - Twilight 👻: Occasionally turns outs into hit by causing the ball to go ethereal, preventing the fielder from catching it.
  - Drizzle 🌧: Causes each inning to start with the previous inning's final batter on second base.
  - Heat Wave 🌄: Occasionally causes pitchers to be relieved by a random player from the lineup.
  - Breezy 🎐: Occasionally swaps letters of a player's name, altering their name for the remainder of the game and changing their stats.
  - Starlight 🌃: The stars are displeased with dingers and will cancel most of them out by pulling them foul.
  - Meteor Shower 🌠: Has a chance to warp runners on base to none base causing them to score.
  - Hurricane 🌀: Flips the scoreboard every few innings.
  - Tornado 🌪: Occasionally shuffles baserunners around to different bases.
  - Torrential Downpour ⛈: The game does not end until one team scores X runs where X is the original inning count of the game, 9 by default.
  - Summer Mist 🌁: When a player hits into an out, they have a chance to get lost in the mist and be temporarily removed from the lineup. If another player gets lost in the mist the first player returns and takes the newly lost player's spot in the lineup.
  - Leaf Eddies 🍂: The visiting team plays all of their outs in a row without inning breaks, then the home team does the same, if the game ends tied, each team plays sudden death 1-out 'golden run' innings until the game is decided.
  - Smog 🚌: Picks a new random weather at the beginning of each inning from: Supernova, Midnight, Slight Tailwind, Twilight, Thinned Veil, Drizzle, Breezy, Starlight, Meteor Shower, Hurricane, Tornado, Summer Mist, and Dusk.
  - Dusk 🌆: New patch weather, its effects will be revealed next time a new weather in implemented.

## Credit
The original project is [Sim16](https://github.com/Sakimori/matteo-the-prestige), created by Sakimori and other contributors, and supported by her Patreon. Inspiration was taken from [Blaseball](https://blaseball.com/) and Out of the Park Baseball. The stats system is based on [blaseball-mike](https://github.com/jmaliksi/blaseball-mike).

This code is licensed under GNU GPL v3, which means you may use, edit, and distribute the code as you wish, as long as you offer others the same freedoms for your version. No warranty is provided for the software. The full license can be viewed at LICENSE.md.