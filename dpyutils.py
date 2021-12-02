from typing import List, Tuple, Union
import discord
from discord.ext import commands


class ButtonPaginator(discord.ui.View):
    def __init__(self, embeds:List[discord.Embed], initiator:discord.Member):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.initiator = initiator
        self.message:Union[discord.Message, None] = None
        self.currentindex = 0

        for e in self.embeds:
            e.set_footer(
                text=f"({self.embeds.index(e)+1}/{len(self.embeds)})  {'' if e.footer.text == discord.Embed.Empty else '• '+ e.footer.text}"
            )
    
    @classmethod
    async def ButtonPaginate(cls, ctx:commands.Context, embeds:List[discord.Embed]):
        if len(embeds) == 1:
            await ctx.send(embed=embeds[0])
            return
        view = cls(embeds, ctx.author)
        view.message = await ctx.reply(embed=embeds[0], view=view)
        return view

    async def interaction_check(self, interaction:discord.Interaction):
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
        self, button: discord.Button, interaction:discord.Interaction=discord.Interaction
    ):
        self.currentindex = 0
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="⬅️")
    async def backwards(self, button: discord.Button, interaction:discord.Interaction=discord.Interaction):
        self.currentindex = self.currentindex - 1 if self.currentindex >= 1 else -1
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="➡️")
    async def forwards(self, button: discord.Button, interaction:discord.Interaction=discord.Interaction):
        try:
            self.embeds[self.currentindex + 1]
            self.currentindex = self.currentindex + 1
        except IndexError:
            self.currentindex = 0
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="⏭️")
    async def fullforwards(
        self, button: discord.Button, interaction:discord.Interaction=discord.Interaction
    ):
        self.currentindex = len(self.embeds) - 1
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="🛑")
    async def stop(self, button: discord.Button, interaction:discord.Interaction=discord.Interaction):
        await self.message.edit(view=None)

class ButtonConfirmation(discord.ui.View):
    def __init__(self, initiator):
        super().__init__(timeout=120)
        self.initiator=initiator
        self.result=None

    async def interaction_check(self, interaction:discord.Interaction):
        if interaction.user.id == self.initiator.id:
            return True

        await interaction.response.send_message("This isn't your confirmation!", ephemeral=True)
        return False

    @discord.ui.button(emoji="✅", style=discord.ButtonStyle.green)
    async def confirm(self, button:discord.Button, interaction=discord.Interaction):
        self.result=True
        self.stop()

    
    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.red)
    async def deny(self, button:discord.Button, interaction=discord.Interaction):
        self.result=False
        self.stop()

async def button_confirm(initiator:discord.Member, channel:discord.TextChannel, prompt:Union[discord.Embed, str], embed=None) -> Tuple[bool, discord.Message]:
    view=ButtonPaginator(initiator)
    message=await channel.send(prompt if embed is None else None, embed=None if embed is None else embed, view=view)
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

    async def callback(self, interaction:discord.Interaction=discord.Interaction):
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

class MoveFlags(commands.FlagConverter, delimiter=' ', prefix='--'):
    name: str