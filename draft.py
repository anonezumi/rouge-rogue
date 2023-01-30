from collections import namedtuple
import game, random, json, uuid, onomancer, discord, team, asyncio

Participant = namedtuple('Participant', ['handle', 'team'])
BOOKMARK = Participant(handle="bookmark", team=None)  # keep track of start/end of draft round


class Draft:
    """
    Represents a draft party with n participants constructing their team from a pool
    of names.
    """

    @classmethod
    def make_draft(cls, teamsize, draftsize, minsize, pitchers):
        draft = cls(teamsize, draftsize, minsize, pitchers)
        return draft

    def __init__(self, teamsize, draftsize, minsize, pitchers):
        self.DRAFT_SIZE = draftsize
        self.REFRESH_DRAFT_SIZE = minsize  # fewer players remaining than this and the list refreshes
        self.DRAFT_ROUNDS = teamsize
        self.pitchers = pitchers
        self._id = str(uuid.uuid4())[:6]
        self._participants = []
        self._active_participant = BOOKMARK  # draft mutex
        nameslist = onomancer.get_names(limit=self.DRAFT_SIZE)
        self._players = nameslist
        self._round = 0

    @property
    def round(self):
        """
        Current draft round. 1 indexed.
        """
        return self._round

    @property
    def active_drafter(self):
        """
        Handle of whomever is currently up to draft.
        """
        return self._active_participant.handle

    @property
    def active_drafting_team(self):
        return self._active_participant.team.name

    def add_participant(self, handle, team_name, slogan):
        """
        A participant is someone participating in this draft. Initializes an empty team for them
        in memory.

        `handle`: discord @ handle, for ownership and identification
        """
        team = game.team()
        team.name = team_name
        team.slogan = slogan
        self._participants.append(Participant(handle=handle, team=team))

    def start_draft(self):
        """
        Call after adding all participants and confirming they're good to go.
        """
        self.advance_draft()

    def refresh_players(self):
        nameslist = onomancer.get_names(limit=self.DRAFT_SIZE)
        self._players = nameslist

    def advance_draft(self):
        """
        The participant list is treated as a circular queue with the head being popped off
        to act as the draftign mutex.
        """
        if self._active_participant == BOOKMARK:
            self._round += 1
        self._participants.append(self._active_participant)
        self._active_participant = self._participants.pop(0)

    def get_draftees(self):
        return list(self._players.keys())

    def draft_player(self, handle, player_name):
        """
        `handle` is the participant's discord handle.
        """
        if self._active_participant.handle != handle:
            raise ValueError(f'{self._active_participant.handle} is drafting, not you')

        player_name = player_name.strip()

        player = self._players.get(player_name)
        if not player:
            # might be some whitespace shenanigans
            for name, stats in self._players.items():
                if name.replace('\xa0', ' ').strip().lower() == player_name.lower():
                    player = stats
                    break
            else:
                # still not found
                raise ValueError(f'Player `{player_name}` not in draft list')
        del self._players[player['name']]

        if len(self._players) <= self.REFRESH_DRAFT_SIZE:
            self.refresh_players()

        if self._round <= self.DRAFT_ROUNDS - self.pitchers:
            self._active_participant.team.add_lineup(game.player(json.dumps(player)))
        else:
            self._active_participant.team.add_pitcher(game.player(json.dumps(player)))

        self.advance_draft()
        if self._active_participant == BOOKMARK:
            self.advance_draft()

        return player

    def get_teams(self):
        teams = []
        if self._active_participant != BOOKMARK:
            teams.append((self._active_participant.handle, self._active_participant.team))
        for participant in self._participants:
            if participant != BOOKMARK:
                teams.append((participant.handle, participant.team))
        return teams

    def finish_draft(self):
        for handle, team in self.get_teams():
            success = game.save_team(team, int(handle[3:-1]))
            if not success:
                raise Exception(f'Error saving team for {handle}')

@discord.app_commands.Command()
async def startdraft(inter: discord.Interaction, participants: str, teamsize: int = 13, draftsize: int = 20, minsize: int = 4, pitchers: int = 3, timeout: int = 120):
    if teamsize-pitchers > 20 or pitchers > 8:
        inter.response.send_message(context="You can't fit that many players on a team, chief. Slow your roll.")
        return
    if teamsize < 3 or pitchers < 1 or draftsize < 5 or minsize < 2:
        inter.response.send_message(context="One of those numbers is too low. Draft size has to be at least 5, the rest should be obvious.")
        return
    if draftsize > 40:
        inter.response.send_message(context="40 players is the max. We're not too confident about pushing for more.")
        return

    # await inter.followup.send("Got it, boss. Give me a sec to find all the paperwork.")

    draft = Draft.make_draft(teamsize, draftsize, minsize, pitchers)

    for i in range(0, len(content), 3):
        handle_token = content[i].strip()
        for mention in mentions:
            if mention in handle_token:
                handle = mention
                break
            else:
                await msg.channel.send(f"I don't recognize {handle_token}.")
                return
        team_name = content[i + 1].strip()
        if game.get_team(team_name):
            await msg.channel.send(f'Sorry {handle}, {team_name} already exists')
            return
        slogan = content[i + 2].strip()
        draft.add_participant(handle, team_name, slogan)

    success = await wait_start(msg.channel, mentions)
    if not success:
        return

    draft.start_draft()
    footer = f"The draft class of {random.randint(2007, 2075)}"
    while draft.round <= draft.DRAFT_ROUNDS:
        message_prefix = f'Round {draft.round}/{draft.DRAFT_ROUNDS}:'
        if draft.round == draft.DRAFT_ROUNDS:
            body = random.choice([
                f"Now just choose a pitcher and we can finish off this paperwork for you, {draft.active_drafter}",
                f"Pick a pitcher, {draft.active_drafter}, and we can all go home happy. 'Cept your players. They'll have to play baseball.",
                f"Almost done, {draft.active_drafter}. Pick your pitcher.",
            ])
            message = f"⚾️ {message_prefix} {body}"
        elif draft.round <= draft.DRAFT_ROUNDS - draft.pitchers:
            body = random.choice([
                f"Choose a batter, {draft.active_drafter}.",
                f"{draft.active_drafter}, your turn. Pick one.",
                f"Pick one to fill your next lineup slot, {draft.active_drafter}.",
                f"Alright, {draft.active_drafter}, choose a batter.",
            ])
            message = f"🏏 {message_prefix} {body}"
        else:
            body = random.choice([
                f"Warning: Pitcher Zone. Enter if you dare, {draft.active_drafter}.",
                f"Time to pitch a picker, {draft.active_drafter}.\nWait, that doesn't sound right.",
                f"Choose a yeeter, {draft.active_drafter}.\nDid we use that word right?",
                f"Choose a pitcher, {draft.active_drafter}."])
            message = f"⚾️ {message_prefix} {body}"
        await msg.channel.send(
            message,
            embed=build_draft_embed(draft.get_draftees(), footer=footer),
        )
        try:
            draft_message = await self.wait_draft(msg.channel, draft, timeout)
            draft.draft_player(f'<@!{draft_message.author.id}>', draft_message.content.split(' ', 1)[1])
        except SlowDraftError:
            player = random.choice(draft.get_draftees())
            await msg.channel.send(f"I'm not waiting forever. You get {player}. Next.")
            draft.draft_player(draft.active_drafter, player)
        except ValueError as e:
            await msg.channel.send(str(e))
        except IndexError:
            await msg.channel.send("Quit the funny business.")

    for handle, team in draft.get_teams():
        await msg.channel.send(
            random.choice([
                f"Done and dusted, {handle}. Here's your squad.",
                f"Behold the {team.name}, {handle}. Flawless, we think.",
                f"Oh, huh. Interesting stat distribution. Good luck, {handle}.",
            ]),
            embed=team.build_team_embed(team),
        )
    try:
        draft.finish_draft()
    except Exception as e:
        await msg.channel.send(str(e))

async def wait_start(self, channel, mentions):
    start_msg = await channel.send("Sound off, folks. 👍 if you're good to go " + " ".join(mentions))
    await start_msg.add_reaction("👍")
    await start_msg.add_reaction("👎")

    def react_check(react, user):
        return f'<@!{user.id}>' in mentions and react.message == start_msg

    while True:
        try:
            react, _ = await client.wait_for('reaction_add', timeout=60.0, check=react_check)
            if react.emoji == "👎":
                await channel.send("We dragged out the photocopier for this! Fine, putting it back.")
                return False
            if react.emoji == "👍":
                reactors = set()
                async for user in react.users():
                    reactors.add(f'<@!{user.id}>')
                if reactors.intersection(mentions) == mentions:
                    return True
        except asyncio.TimeoutError:
            await channel.send("Y'all aren't ready.")
            return False
    return False

async def wait_draft(self, channel, draft, timeout):
    def check(m):
        if m.channel != channel:
            return False
        if m.content.startswith('d ') or m.content.startswith('draft '):
            return True
        for prefix in config['prefix']:
            if m.content.startswith(prefix + 'draft '):
                return True
        return False

    try:
        draft_message = await client.wait_for('message', timeout=timeout, check=check)
    except asyncio.TimeoutError:
        raise SlowDraftError('Too slow, boss.')
    return draft_message

def build_draft_embed(names, title="The Draft", footer="You must choose"):
    embed = discord.Embed(color=discord.Color.purple(), title=title)
    column_size = 7
    for i in range(0, len(names), column_size):
        draft = '\n'.join(names[i:i + column_size])
        embed.add_field(name="-", value=draft, inline=True)
    embed.set_footer(text=footer)
    return embed

COMMANDS = [startdraft]