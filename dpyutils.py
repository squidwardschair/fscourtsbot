from typing import List, Tuple, Union
import discord
from discord.ext import commands
from datetime import datetime

class WarrantRequestInit(discord.ui.View):
    def __init__(self, db_pool, channel):
        super().__init__(timeout=None)
        self.db_pool = db_pool
        self.channel = channel

    @discord.ui.button(
        label="Request a warrant",
        style=discord.ButtonStyle.red,
        custom_id="warrant_req_message",
    )
    async def request_warrant(
        self,
        interaction: discord.Interaction,
        button: discord.Button,
    ):
        view = view = WarrantRequestForm(self.db_pool, self.channel)
        embed = discord.Embed(
            title="Uniform Warrant Request System",
            timestamp=discord.utils.utcnow(),
            color=discord.Color.dark_gold(),
            description="Select the type of warrant that you are requesting using the drop-down menu below. This request will timeout in 15 minutes.",
        )
        embed.add_field(
            name="Arrest warrant",
            value="""Arrest warrants require evidence **beyond a reasonable doubt**. That means there should be no question that the suspect committed the crime(s) alleged.
Do not request an arrest warrant if the suspect has already been arrested.
Do not request an arrest warrant for traffic infractions or minor crimes.
Do not request an arrest warrant for complex crimes, such as corruption or treason. Instead, contact the Department of Justice.""",
            inline=False,
        )
        embed.add_field(
            name="Search warrant",
            value="""Search warrants require evidence that establishes probable cause that a crime has been committed **and** that evidence, contraband, or proceeds of that crime will be found in the search.
You can request a search warrant for a storage unit at Rage Storage.
You can also request a search warrant to search a person or some property.""",
            inline=False,
        )
        view.message = await interaction.user.send(embed=embed, view=view)
        await interaction.response.send_message(
            "Request form sent to your DMs.", ephemeral=True
        )
        async with await self.db_pool.acquire() as cnc:
            await cnc.execute("INSERT INTO current_requests(userid) VALUES(?);", interaction.user.id)
            await cnc.commit()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        async with await self.db_pool.acquire() as cnc:
            timestamp_cursor = await cnc.fetchall("SELECT timestamp FROM warrantrequests WHERE discord_id=?", interaction.user.id)
            curr_req_cursor = await cnc.fetchall("SELECT userid FROM current_requests WHERE userid=?", interaction.user.id)
            timestamps = list(timestamp_cursor)
        if curr_req_cursor:
            await interaction.response.send_message("You have an ongoing request, please complete or cancel that request before submitting another one.", ephemeral=True)
            return False
        now=datetime.utcnow()
        if len(timestamps)>2:
            new_times = []
            for time in timestamps:
                print(type(dict(time)['timestamp']))
                new_times.append(datetime.strptime(dict(time)['timestamp'], "%Y-%m-%d %H:%M:%S"))
            first_diff = (now-new_times[-1]).total_seconds()
            second_diff = (now-new_times[-2]).total_seconds()
            print(first_diff+second_diff)
            if (first_diff+second_diff) < 300:
                await interaction.response.send_message("You can only submit two requests every five minutes.", ephemeral=True)
                return False
        return True
class WarrantRequestForm(discord.ui.View):
    def __init__(self, db_pool, channel):
        super().__init__(timeout=900)
        self.message: Union[None, discord.Message] = None
        self.db_pool=db_pool
        self.add_item(WarrantTypeSelect(db_pool, channel))

    async def on_timeout(self):
        await self.message.edit("15 minute timeout reached, request expired.", embed=None, view=None)
        async with await self.db_pool.acquire() as cnc:
            await cnc.execute("DELETE FROM current_requests WHERE userid=?;", self.message.channel.recipient.id)
            await cnc.commit()

    @discord.ui.button(label="Cancel request", style=discord.ButtonStyle.red, row=1)
    async def cancel_request(
        self,
        interaction: discord.Interaction,
        button: discord.Button,
    ):
        await interaction.message.delete()
        await interaction.response.send_message("Request cancelled.", ephemeral=True)
        async with await self.db_pool.acquire() as cnc:
            await cnc.execute("DELETE FROM current_requests WHERE userid=?;", interaction.user.id)
            await cnc.commit()
class WarrantTypeSelect(discord.ui.Select):
    def __init__(self, db_pool, channel):
        super().__init__(placeholder="Select warrant type", row=0)
        self.add_option(
            label="Arrest warrant",
        )
        self.add_option(
            label="Search warrant",
        )
        self.db_pool = db_pool
        self.channel = channel

    async def callback(self, interaction: discord.Interaction = discord.Interaction):
        await interaction.response.send_modal(RequestForm(self.db_pool, self.channel, interaction.data["values"][0]))


class RequestForm(discord.ui.Modal):
    username = discord.ui.TextInput(
        label="What is your username?",
        min_length=3,
        max_length=20,
        style=discord.TextStyle.short,
        required=True,
    )
    warrant_against = discord.ui.TextInput(
        label="Against whom are you requesting a warrant?",
        min_length=3,
        max_length=500,
        style=discord.TextStyle.long,
        required=True,
        placeholder="Provide a link to the Roblox profile of the person against whom you are requesting a warrant."
    )
    crimes = discord.ui.TextInput(
        label="What crimes have been committed?",
        min_length=5,
        max_length=500,
        style=discord.TextStyle.long,
        required=True,
    )
    evidence_insertion = discord.ui.TextInput(
        label="Evidence insertion",
        placeholder="Please provide evidence that meets the requirements for your specified warrant.",
        min_length=5,
        max_length=1000,
        style=discord.TextStyle.long,
        required=True,
    )

    statement_of_facts = discord.ui.TextInput(
        label="Statement of facts",
        min_length=5,
        max_length=1000,
        style=discord.TextStyle.long,
        required=True,
        placeholder="Provide a statement of facts explaining the facts and circumstances to support issuing a warrant.",
    )

    def __init__(self, db_pool, channel, type_warrant):
        super().__init__(title="Warrant request submission form")
        self.db_pool = db_pool
        self.channel = channel
        self.type_warrant = type_warrant
        self.message: Union[discord.Message, None] = None
        if self.type_warrant == "Search warrant":
            self.warrant_against.label="What should be searched for and where?"
            self.warrant_against.placeholder="Also link the property owner's Roblox profile."


    async def on_submit(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="Oath Affirmation",
            color=discord.Color.dark_gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Warrant type", value=self.type_warrant)
        embed.add_field(name="What is your rank, username and department?", value=self.username, inline=False)
        embed.add_field(
            name="Against whom are you requesting a warrant?",
            value=self.warrant_against,
            inline=False
        )
        embed.add_field(name="What crimes have been committed?", value=self.crimes, inline=False)
        embed.add_field(name="Evidence insertion", value=self.evidence_insertion, inline=False)
        embed.add_field(name="Statement of facts", value=self.statement_of_facts, inline=False)
        embed.add_field(
            name="Do you agree to submit this request under penalty of perjury?",
            value="Select the button below to affirm the oath and submit your warrant request.",
        )
        await interaction.message.delete()
        view = WarrantConfirmation(self.db_pool, self.channel, embed, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_message()

class WarrantConfirmation(discord.ui.View):
    def __init__(self, db_pool, channel: discord.TextChannel, embed: discord.Embed, userid: int):
        super().__init__(timeout=120)
        self.db_pool = db_pool
        self.embed = embed
        print(channel)
        self.request_channel = channel
        self.message: Union[discord.Message, None] = None
        self.userid=userid
        self.completed = False

    @discord.ui.button(label="I do", style=discord.ButtonStyle.green)
    async def request_warrant(
        self,
        interaction: discord.Interaction,
        button: discord.Button,
    ):
        curr_time = discord.utils.utcnow()
        
        async with await self.db_pool.acquire() as cnc:
            id_cursor = await cnc.fetchone("SELECT request_id FROM warrantrequests ORDER BY request_id DESC LIMIT 1;")
            if not last_id:
                last_id=0
            else:
                last_id = dict(id_cursor)['request_id']
        new_id=last_id+1
        if new_id<100:
            for i in range(3-(len(str(new_id)))):
                new_id="0"+str(new_id)
        print(new_id)
        self.embed.set_footer(text=f"W-{curr_time.strftime('%m%d%y')}-{new_id}")
        self.embed.title="Submitted warrant request"
        self.embed.description = f"Submitted by user <@{interaction.user.id}> at {curr_time.strftime('%m/%d/%y %H:%M:%S')} UTC."
        view=WarrantRequestTools(self.db_pool)
        req_msg=await self.request_channel.send(embed=self.embed, view=view)
        async with await self.db_pool.acquire() as cnc:
            await cnc.execute(
                "INSERT INTO warrantrequests(discord_id, message_id, claimed, completed) VALUES(?, ?, ?, ?);",
                (interaction.user.id, req_msg.id, False, False),
            )
            await cnc.commit()
        self.embed.title="Submitted warrant request"
        await interaction.response.edit_message(embed=self.embed, view=None)
        self.completed=True
        async with await self.db_pool.acquire() as cnc:
            await cnc.execute("DELETE FROM current_requests WHERE userid=?;", interaction.user.id)
            await cnc.commit()
    
    @discord.ui.button(label="Cancel request", style=discord.ButtonStyle.red)
    async def cancel_request(
        self,
        interaction: discord.Interaction,
        button: discord.Button,
    ):
    
        await interaction.message.delete()
        await interaction.response.send_message("Request cancelled.", ephemeral=True)
        async with await self.db_pool.acquire() as cnc:
            await cnc.execute("DELETE FROM current_requests WHERE userid=?;", interaction.user.id)
            await cnc.commit()

    async def on_timeout(self):
        if not self.completed:
            await self.message.edit("2 minute confirmation timeout reached, request expired.", embed=None, view=None)
            async with await self.db_pool.acquire() as cnc:
                await cnc.execute("DELETE FROM current_requests WHERE userid=?;", self.userid)
                await cnc.commit()
class WarrantRequestTools(discord.ui.View):
    def __init__(self, db_pool):
        super().__init__(timeout=None)
        self.claimed_judge = None
        self.db_pool=db_pool
        self.message: Union[discord.Message, None] = None

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.gray)
    async def claim_request(
        self,
        interaction: discord.Interaction,
        button: discord.Button,
    ):
        self.claimed_judge = interaction.user
        button.disabled = True
        button.label = f"Claimed by {self.claimed_judge.name}"
        self.children[1].disabled=False
        self.children[2].disabled=False
        self.children[3].disabled=False
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Unclaim", style=discord.ButtonStyle.gray, disabled=True)
    async def unclaim_request(
        self,
        interaction: discord.Interaction,
        button: discord.Button,
    ):
        self.claimed_judge = None
        button.disabled = True
        self.children[0].label = f"Claim"
        self.children[0].disabled=False
        self.children[2].disabled=True
        self.children[3].disabled=True
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.claimed_judge:
            if interaction.user!=self.claimed_judge:
                await interaction.response.send_message("You haven't claimed this warrant request.", ephemeral=True)
            else:
                return True
        return True
        
    @discord.ui.button(label="Accept request", style=discord.ButtonStyle.green, disabled=True)
    async def accept_request(
        self,
        interaction: discord.Interaction,
        button: discord.Button,
    ):
        async with await self.db_pool.acquire() as cnc:
            user_cursor = await cnc.fetchone("SELECT timestamp,request_id,discord_id FROM warrantrequests WHERE message_id=?;", (interaction.message.id))
            user = interaction.client.get_user(int(dict(user_cursor)['discord_id']))
            id = dict(user_cursor)['request_id']
            timestamp = dict(user_cursor)['timestamp']

        await interaction.response.send_modal(CallbackForm(True, user, interaction.user, interaction.message.embeds[0], id, timestamp))

    @discord.ui.button(label="Deny request", style=discord.ButtonStyle.red, disabled=True)
    async def deny_request(
        self,
        interaction: discord.Interaction,
        button: discord.Button,
    ):
        async with await self.db_pool.acquire() as cnc:
            user_cursor = await cnc.fetchone("SELECT timestamp,request_id,discord_id FROM warrantrequests WHERE message_id=?;", (interaction.message.id))
            user = interaction.client.get_user(int(dict(user_cursor)['discord_id']))
            id = dict(user_cursor)['request_id']
            timestamp = dict(user_cursor)['timestamp']
        await interaction.response.send_modal(CallbackForm(False, user, interaction.user, interaction.message.embeds[0], id, timestamp))
        

class CallbackForm(discord.ui.Modal):
    message = discord.ui.TextInput(
        label="Message to warrant requester (optional)",
        max_length=2000,
        style=discord.TextStyle.long,
        required=False,
    )
    warrant_link = discord.ui.TextInput(label="Warrant link (if applicable)", min_length=5, max_length=200, style=discord.TextStyle.short, required=False)
    def __init__(self, accepted:bool, user:discord.User, judge:discord.User, embed:discord.Embed, id:str, timestamp: str):
        super().__init__(title="Resolve warrant request")
        self.accepted = accepted
        self.user=user
        self.judge = judge
        self.embed=embed
        self.id=id
        self.timestamp=timestamp

    async def on_submit(self, interaction: discord.Interaction):
        if self.id<100:
            for i in range(3-(len(str(self.id)))):
                self.id="0"+str(self.id)
        if isinstance(self.message, str):
            message_part = ' A message regarding this decision from the court official who viewed your warrant request is below.\n\n```'+self.message+'```'
        else:
            message_part=None
        await self.user.send(f"Your warrant request with ID `W-{datetime.strptime(self.timestamp, '%Y-%m-%d %H:%M:%S').strftime('%m%d%y')}-{self.id}` was **{'ACCEPTED' if self.accepted else 'DENIED'}** by <@{self.judge.id}>.{f' The warrant link can be accessed [here]({self.warrant_link}).' if self.accepted else ''}{message_part if message_part else ''}")
        self.embed.title="Resolved warrant request"
        view=discord.ui.View()
        view.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label=f"Resolved by {interaction.user.name}", disabled=True))
        await interaction.response.edit_message(embed=self.embed, view=view)
class ButtonPaginator(discord.ui.View):
    def __init__(self, embeds: List[discord.Embed], initiator: discord.Member):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.initiator = initiator
        self.message: Union[discord.Message, bool] = None
        self.currentindex = 0

        for e in self.embeds:
            e.set_footer(
                text=f'({self.embeds.index(e) + 1}/{len(self.embeds)})  {"" if e.footer.text == discord.Embed.Empty else f"• {e.footer.text}"}'
            )

    @classmethod
    async def ButtonPaginate(cls, ctx: commands.Context, embeds: List[discord.Embed]):
        if len(embeds) == 1:
            await ctx.send(embed=embeds[0])
            return
        view = cls(embeds, ctx.author)
        view.message = await ctx.reply(embed=embeds[0], view=view)
        return view

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.initiator.id:
            return True

        await interaction.response.send_message(
            "This isn't your paginator!", ephemeral=True
        )
        return False

    async def on_timeout(self):
        await self.message.edit(view=None)

    @discord.ui.button(emoji="⏮️")
    async def fullbackwards(
        self,
        button: discord.Button,
        interaction: discord.Interaction = discord.Interaction,
    ):
        self.currentindex = 0
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="⬅️")
    async def backwards(
        self,
        button: discord.Button,
        interaction: discord.Interaction = discord.Interaction,
    ):
        self.currentindex = self.currentindex - 1 if self.currentindex >= 1 else -1
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="➡️")
    async def forwards(
        self,
        button: discord.Button,
        interaction: discord.Interaction = discord.Interaction,
    ):
        try:
            self.embeds[self.currentindex + 1]
            self.currentindex = self.currentindex + 1
        except IndexError:
            self.currentindex = 0
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="⏭️")
    async def fullforwards(
        self,
        button: discord.Button,
        interaction: discord.Interaction = discord.Interaction,
    ):
        self.currentindex = len(self.embeds) - 1
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="🛑")
    async def stop(
        self,
        button: discord.Button,
        interaction: discord.Interaction = discord.Interaction,
    ):
        await self.message.edit(view=None)


class ButtonConfirmation(discord.ui.View):
    def __init__(self, initiator):
        super().__init__(timeout=120)
        self.initiator = initiator
        self.result = None

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.initiator.id:
            return True

        await interaction.response.send_message(
            "This isn't your confirmation!", ephemeral=True
        )
        return False

    @discord.ui.button(emoji="✅", style=discord.ButtonStyle.grey)
    async def confirm(self, button: discord.Button, interaction=discord.Interaction):
        self.result = True
        self.stop()

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.grey)
    async def deny(self, button: discord.Button, interaction=discord.Interaction):
        self.result = False
        self.stop()


async def button_confirm(
    initiator: discord.Member,
    channel: discord.TextChannel,
    prompt: Union[discord.Embed, str],
    embed=None,
) -> Tuple[bool, discord.Message]:
    view = ButtonConfirmation(initiator)
    message = await channel.send(
        prompt if embed is None else None,
        embed=None if embed is None else embed,
        view=view,
    )
    await view.wait()
    return view.result, message


class HelpSelect(discord.ui.Select):
    def __init__(self, embeddict, initiator):
        super().__init__(placeholder="Select a command", row=0)
        self.embeddict = embeddict
        self.initiator = initiator
        self.message = None
        for option in self.embeddict:
            self.add_option(
                label=option,
                description=self.embeddict[option][0],
                emoji=self.embeddict[option][1],
            )

    async def callback(self, interaction: discord.Interaction = discord.Interaction):
        await interaction.message.edit(
            embed=self.embeddict[interaction.data["values"][0]][2]
        )


class HelpView(discord.ui.View):
    def __init__(self, embeddict, initiator):
        super().__init__(timeout=180)
        self.initator = initiator
        self.add_item(HelpSelect(embeddict, initiator))

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.initator.id

    async def on_timeout(self: discord.ui.View):
        await self.message.edit(view=None)


class CourtHelp(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs=dict(hidden=True))

    def get_command_signature(self, command: commands.Command, context=None):
        ctx = self.context if context is None else context
        return f"{ctx.clean_prefix}{command.qualified_name} {command.signature}"

    def get_command_name(self, command: commands.Command):
        return f"{command.qualified_name}"

    async def send_all_help(self, *args, **kwargs):
        ctx: commands.Context = self.context
        embed = discord.Embed(
            title="Firestone Court Utilities Help",
            description=f"This bot is a utilities bot for the Firestone Courts that allows you to find your own cases, search for cases, and send automatic messages when cases are declined and expungements are completed. Use the dropdown menu to navigate through the commands.\n\n **Automatic Notifications**\nThe bot is on a 2 minute loop that checks for cases that have been completed. The bot will notify you for completed expungements with a copy of the card comments and the verdict, as well as declined cases with the same information.\n\n**{ctx.guild.name}'s prefix:** `{ctx.clean_prefix}`",
            timestamp=discord.utils.utcnow(),
            color=discord.Color.teal(),
        )
        embeds = {"Main Help Page": ["The main page for the help command", "🔷", embed]}
        emojis = {
            "search": "🔍",
            "botinfo": "ℹ️",
            "caseinfo": "📚",
            "expungify": "〽️",
            "wordle": "🇼",
        }
        filtercommands: List[commands.Command] = await self.filter_commands(
            ctx.bot.commands, sort=True
        )
        for command in filtercommands:
            if command.name in ["reload", "reloadlists", "reloadready"]:
                continue
            embed.add_field(
                name=self.get_command_signature(command), value=command.brief
            )
            embeds[command.name] = [
                command.brief,
                emojis[command.name],
                await self.send_command_help(command, fake=True),
            ]
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Created by MrApples#2555, contact me for bugs")
        embed.set_thumbnail(url=ctx.me.display_avatar.url)
        view = HelpView(embeds, ctx.author)
        view.message = await ctx.reply(embed=embed, view=view)

    send_bot_help = send_cog_help = send_group_help = send_all_help

    async def send_command_help(
        self, command: commands.Command, fake=False, context=None
    ):
        ctx = self.context if context is None else context
        embed = discord.Embed(
            title=f"{ctx.clean_prefix}{command}",
            description=command.help,
            color=discord.Color.teal(),
        )
        embed.add_field(
            name="Usage",
            value=f"`{self.get_command_signature(command, context=context)}`",
            inline=True,
        )
        if command._buckets and (cooldown := command._buckets._cooldown):
            embed.add_field(
                name="Cooldown", value=f"{cooldown.per:.0f} seconds", inline=True
            )
        if command.aliases:
            embed.add_field(name="Alias", value=",".join(command.aliases), inline=True)
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.set_thumbnail(url=ctx.me.display_avatar.url)
        embed.set_footer(
            text=f"Do {ctx.clean_prefix}help for more information | <> is required | [] is optional"
        )
        if fake is True:
            return embed
        await ctx.reply(embed=embed)

    async def send_error_message(self, error):
        embed = discord.Embed(title="Help not found!", description=error)
        await self.context.send(embed=embed)


class MoveFlags(commands.FlagConverter, delimiter=" ", prefix="--"):
    judge: str
