import discord

class ButtonPaginator(discord.ui.View):
    def __init__(self, embeds, initiator):
        super().__init__(timeout=120)
        self.embeds=embeds
        self.initiator=initiator
        self.message=None
        self.currentindex=0

        for e in self.embeds:
            e.set_footer(text=f"({self.embeds.index(e)+1}/{len(self.embeds)})  {'' if e.footer.text == discord.Embed.Empty else '• '+ e.footer.text}")

    async def interaction_check(self, interaction):
        if interaction.user.id != self.initiator.id:
            await interaction.response.send_message("This isn't your paginator!", ephemeral=True)
            return False
        else:
            return True

    async def on_timeout(self):
        await self.message.edit(view=None)

    @discord.ui.button(emoji="⏮️")
    async def fullbackwards(self, button:discord.Button, interaction=discord.Interaction):
        self.currentindex=0
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="⬅️")
    async def backwards(self, button:discord.Button, interaction=discord.Interaction):
        self.currentindex=self.currentindex-1 if self.currentindex-1>=0 else -1
        await interaction.message.edit(embed=self.embeds[self.currentindex])
    
    @discord.ui.button(emoji="➡️")
    async def forwards(self, button:discord.Button, interaction=discord.Interaction):
        try:
            self.embeds[self.currentindex+1]
            self.currentindex=self.currentindex+1
        except IndexError:
            self.currentindex=0
        await interaction.message.edit(embed=self.embeds[self.currentindex])

    @discord.ui.button(emoji="⏭️")
    async def fullforwards(self, button:discord.Button, interaction=discord.Interaction):
        self.currentindex=len(self.embeds)-1
        await interaction.message.edit(embed=self.embeds[self.currentindex])
    
    @discord.ui.button(emoji="🛑")
    async def stop(self, button:discord.Button, interaction=discord.Interaction):
        await self.message.edit(view=None)

async def ButtonPaginate(ctx, embeds, initiator):
    if len(embeds)==1:
        await ctx.send(embed=embeds[0])
        return
    view=ButtonPaginator(embeds, initiator)
    view.message=await ctx.reply(embed=embeds[0], view=view)