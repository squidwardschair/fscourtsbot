from typing import List, Tuple, Union
import discord
from discord.ext import commands


class ButtonPaginator(discord.ui.View):
    def __init__(self, embeds: List[discord.Embed], initiator: discord.Member):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.initiator = initiator
        self.message: Union[discord.Message, bool] = None
        self.currentindex = 0

        for e in self.embeds:
            e.set_footer(
                text=f"({self.embeds.index(e)+1}/{len(self.embeds)})  {'' if e.footer.text == discord.Embed.Empty else '• '+ e.footer.text}"
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
        emojis = {"search": "🔍", "botinfo": "ℹ️", "caseinfo": "📚", "expungify": "〽️"}
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
