import discord
from discord.ext import commands, tasks
import aiohttp
import config
from buttonpaginator import HelpView
import pathlib

class CourtsBot(commands.Bot):
    def __init__(self):
        super().__init__(intents=discord.Intents.all(), command_prefix=commands.when_mentioned_or("?"), case_insensitive=True, help_command=CourtHelp())
        self.uptime=discord.utils.utcnow()
        self.customfields={}
        self.lists={}
        self.boardids={"593b1c584d118d054065481d": "District Court of Firestone", "581f9473930c99e72f209b09": "Firestone Courts Case Submission Center"}
        self.members={}
        self.cardlist=None
        self.guild=None
        self.owner=None
        self.loc=None

    async def close(self):
        await self.session.close()
        await super().close()

    async def on_connect(self):
        self.session=aiohttp.ClientSession(loop=self.loop)

    async def check_trello(self):
        async with self.session.get("https://api.trello.com/1/boards/593b1c584d118d054065481d") as c:
            if c.status!=200:
                return False
            else:
                return True

    def run_bot(self):
        p = pathlib.Path('./')
        count=0
        for f in p.rglob('*.py'):
            if str(f).startswith("config"):
                continue
            with f.open(encoding='utf8') as of:
                for l in of.readlines():
                    count += 1
        self.loc=count
        self.load_extension("corecommands")
        self.run(config.TOKEN)

class CourtHelp(commands.HelpCommand):
    def __init__(self):
        super().__init__(command_attrs=dict(hidden=True))

    def get_command_signature(self, command):
        ctx=self.context
        return f'{ctx.clean_prefix}{command.qualified_name} {command.signature}'

    def get_command_name(self, command):
        return f'{command.qualified_name}'

    async def send_all_help(self, *args, **kwargs):
        ctx=self.context
        embed=discord.Embed(title="Firestone Court Utilities Help", description=f"This bot is a utilities bot for the Firestone Courts that allows you to find your own cases, search for cases, and send automatic messages when cases are declined and expungements are completed. Use the dropdown menu to navigate through the commands.\n\n **Automatic Notifications**\nThe bot is on a 2 minute loop that checks for cases that have been completed. The bot will notify you for completed expungements with a copy of the card comments and the verdict, as well as declined cases with the same information.\n\n**{ctx.guild.name}'s prefix:** `{ctx.clean_prefix}`", timestamp=discord.utils.utcnow(), color=discord.Color.teal())
        embeds={"Main Help Page": ["The main page for the help command", "🔷", embed]}
        emojis={"search": "🔍", "botinfo": "ℹ️", "caseinfo": "📚"}
        filtercommands=await self.filter_commands(ctx.bot.commands, sort=True)
        for command in filtercommands:
            if command.name=="reload":
                continue
            embed.add_field(name=self.get_command_signature(command), value=command.brief)
            embeds[command.name]=[command.brief, emojis[command.name], await self.send_command_help(command, fake=True)]
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Created by MrApples#2555, contact me for bugs")
        embed.set_thumbnail(url=ctx.me.display_avatar.url)
        view=HelpView(embeds, ctx.author)
        view.message=await ctx.reply(embed=embed, view=view)

    send_bot_help = send_cog_help = send_group_help = send_all_help

    async def send_command_help(self, command, fake=False):
        ctx=self.context
        embed=discord.Embed(title=f"{ctx.clean_prefix}{command}", description=command.help, color=discord.Color.teal())
        embed.add_field(name="Usage", value=f"`{self.get_command_signature(command)}`", inline=True)
        if command._buckets and (cooldown := command._buckets._cooldown):
          embed.add_field(name="Cooldown", value=f"{cooldown.per:.0f} seconds", inline=True)
        if command.aliases:
          embed.add_field(name="Alias", value=",".join(command.aliases), inline=True)
        embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
        embed.set_thumbnail(url=ctx.me.display_avatar.url)   
        embed.set_footer(text=f"Do {ctx.clean_prefix}help for more information | <> is required | [] is optional")
        if fake is True:
            return embed
        await ctx.reply(embed=embed)

    async def send_error_message(self, error):
      embed = discord.Embed(title="Help not found!", description=error)
      channel = self.get_destination()
      await channel.send(embed=embed)  

bot=CourtsBot()

@bot.event
async def on_ready():
    bot.guild=bot.get_guild(875457215727816805)
    bot.owner=bot.get_user(474744664449089556)
    checktrello=await bot.check_trello()
    if checktrello is False:
        await bot.owner.send("trello is down auto shutdown")
        print("trello is down")
        await bot.close()
    cfitems=['5c3bcd0f80f20614a4c72093', '5b08b5face269325c8ed581d', '5b06d74758c55f9759d896df', '5b06d1c81e3ecc5e2f288da7', '5bca6f3c24afea5d2b007136', '5c54684b92c5f91774896b08']
    for item in cfitems:
        async with bot.session.get(f"https://api.trello.com/1/customFields/{item}") as i:
            info=await i.json()
        for option in info['options']:
            bot.customfields[option['id']] = [info['name'], option['value']['text']]
    for board in bot.boardids:
        async with bot.session.get(f"https://api.trello.com/1/boards/{board}/lists") as b:
            info=await b.json()
        for list in info:
            bot.lists[list['id']]=list['name']
    async with bot.session.get(f"https://api.trello.com/1/list/593b1c5e82af460cb51b61c7/cards") as c:
        cinfo=await c.json()
    for member in cinfo:
        if member['name']=='---':
            continue
        getname=member['name'].split(" ")
        bot.members[member['idMembers'][0]]=getname[-1]
    print("bot is ready")

@bot.check
async def block_dms(ctx):
    return ctx.guild is not None

bot.run_bot()