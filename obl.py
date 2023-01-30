
class OBLExplainCommand(Command):
    name = "oblhelp"
    template = "m;oblhelp"
    description = "Explains the One Big League!"

    async def execute(self, msg, command, flags):
        await msg.channel.send("""The One Big League, or OBL, is an asynchronous league that includes every team in the simsim's database. To participate, just use the m;oblteam command with your team of choice. **No signup is required!** This will give you a list of five opponents; playing against one of them and winning nets you a point, and will refresh the list with five new opponents. **Losing results in no penalty!** Each meta-season will last for a few weeks, after which the leaderboards are reset to start the race again!

Look out for the people wrestling emoji, which indicates the potential for a :people_wrestling:Wrassle Match:people_wrestling:, where both teams are on each others' lists and both have the opportunity to score a point. Team rankings and points can also be viewed in the m;oblteam command, and the overall OBL leaderboard can be checked with the m;oblstandings command. Best of luck!!
""")

class OBLLeaderboardCommand(Command):
    name = "oblstandings"
    template = "m;oblstandings"
    description = "Displays the 15 teams with the most OBL points in this meta-season."
         
    async def execute(self, msg, command, flags):
        leaders_list = db.obl_leaderboards()[:15]
        leaders = []
        rank = 1
        for team, points in leaders_list:
            leaders.append({"name" : team, "points" : points})
            rank += 1

        embed = discord.Embed(color=discord.Color.red(), title="The One Big League")
        for index in range(0, len(leaders)):
            embed.add_field(name=f"{index+1}. {leaders[index]['name']}", value=f"{leaders[index]['points']} points" , inline = False)
        await msg.channel.send(embed=embed)

class OBLTeamCommand(Command):
    name = "oblteam"
    template = "m;oblteam [team name]"
    description = "Displays a team's rank, current OBL points, and current opponent selection."

    async def execute(self, msg, command, flags):
        team = get_team_fuzzy_search(command.strip())
        if team is None:
            raise CommandError("Sorry boss, we can't find that team.")

        rival_team = None
        points, beaten_teams_list, opponents_string, rank, rival_name = db.get_obl_stats(team, full=True)
        opponents_list = db.newline_string_to_list(opponents_string)
        for index in range(0, len(opponents_list)):
            oppteam = get_team_fuzzy_search(opponents_list[index])
            opplist = db.get_obl_stats(oppteam)[1]
            if team.name in opplist:
                opponents_list[index] = opponents_list[index] + " 🤼"
            if rival_name == opponents_list[index]:
                opponents_list[index] = opponents_list[index] + " 😈"
        if rival_name is not None:
            rival_team = game.get_team(rival_name)
        opponents_string = db.list_to_newline_string(opponents_list)

        embed = discord.Embed(color=discord.Color.red(), title=f"{team.name} in the One Big League")
        embed.add_field(name="OBL Points", value=points)
        embed.add_field(name="Rank", value=rank)
        embed.add_field(name="Bounty Board", value=opponents_string, inline=False)
        if rival_team is not None:
            r_points, r_beaten_teams_list, r_opponents_string, r_rank, r_rival_name = db.get_obl_stats(rival_team, full=True)
            embed.add_field(name="Rival", value=f"**{rival_team.name}**: Rank {r_rank}\n{rival_team.slogan}\nPoints: {r_points}")
            if r_rival_name == team.name:
                embed.set_footer(text="🔥")
        else:
            embed.set_footer(text="Set a rival with m;oblrival!")
        await msg.channel.send(embed=embed)

class OBLSetRivalCommand(Command):
    name = "oblrival"
    template = "m;oblrival\n[your team name]\n[rival team name]"
    description = "Sets your team's OBL rival. Can be changed at any time. Requires ownership."

    async def execute(self, msg, command, flags):
        try:
            team_i = get_team_fuzzy_search(command.split("\n")[1].strip())
            team_r = get_team_fuzzy_search(command.split("\n")[2].strip())
        except IndexError:
            raise CommandError("You didn't give us enough lines. Command on the top, your team in the middle, and your rival at the bottom.")
        team, owner_id = game.get_team_and_owner(team_i.name)
        if team is None or team_r is None:
            raise CommandError("Can't find one of those teams, boss. Typo?")
        elif owner_id != msg.author.id and msg.author.id not in config()["owners"]:
            raise CommandError("You're not authorized to mess with this team. Sorry, boss.")
        try:
            db.set_obl_rival(team, team_r)
            await msg.channel.send("One pair of mortal enemies, coming right up. Unless you're more of the 'enemies to lovers' type. We can manage that too, don't worry.")
        except:
            raise CommandError("Hm. We don't think that team has tried to do anything in the One Big League yet, so you'll have to wait for consent. Get them to check their bounty board.")

class OBLConqueredCommand(Command):
    name = "oblwins"
    template = "m;oblwins [team name]"
    description = "Displays all teams that a given team has won points off of."

    async def execute(self, msg, command, flags):
        team = get_team_fuzzy_search(command.strip())
        if team is None:
            raise CommandError("Sorry boss, we can't find that team.")

        points, teams, oppTeams, rank, rivalName = db.get_obl_stats(team, full=True)
        pages = []
        page_max = math.ceil(len(teams)/25)

        title_text = f"Rank {rank}: {team.name}"

        for page in range(0,page_max):
            embed = discord.Embed(color=discord.Color.red(), title=title_text)
            embed.set_footer(text = f"{points} OBL Points")
            for i in range(0,25):             
                try:
                    thisteam = game.get_team(teams[i+25*page])
                    if thisteam.slogan.strip() != "":
                        embed.add_field(name=thisteam.name, value=thisteam.slogan)
                    else:
                        embed.add_field(name=thisteam.name, value="404: Slogan not found")
                except:
                    break
            pages.append(embed)

        teams_list = await msg.channel.send(embed=pages[0])
        current_page = 0

        if page_max > 1:
            await teams_list.add_reaction("◀")
            await teams_list.add_reaction("▶")

            def react_check(react, user):
                return user == msg.author and react.message == teams_list

            while True:
                try:
                    react, user = await client.wait_for('reaction_add', timeout=60.0, check=react_check)
                    if react.emoji == "◀" and current_page > 0:
                        current_page -= 1
                        await react.remove(user)
                    elif react.emoji == "▶" and current_page < (page_max-1):
                        current_page += 1
                        await react.remove(user)
                    await teams_list.edit(embed=pages[current_page])
                except asyncio.TimeoutError:
                    return

class OBLResetCommand(Command):
    name = "oblreset"
    template = "m;oblreset"
    description = "NUKES THE OBL BOARD. BE CAREFUL."

    def isauthorized(self, user):
        return user.id in config()["owners"]

    async def execute(self, msg, command, flags):
        if self.isauthorized(msg.author):
            db.clear_obl()
            await msg.channel.send("💣")