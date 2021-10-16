import datetime
import discord
from discord.ext import tasks, commands
from buttonpaginator import ButtonPaginate
from dateutil import parser
import traceback
import time
from psutil import Process, cpu_percent
from os import getpid

class CoreCommands(commands.Cog):
    def __init__(self, bot):
        self.bot=bot
        self.checklist.start()

    async def command_help_format(command, ctx):
        if command._buckets and (cooldown := command._buckets._cooldown):
            saying=f"**Cooldown:** {cooldown.per:.0f} seconds \n"
        else:
            saying=""
        embed=discord.Embed(title=f"Command: {command.name}", description=f"**Description:** {command.short_doc} \n {saying} **Format:** {ctx.clean_prefix}{command.qualified_name} {command.signature} \n **Category:** {command.cog_name or 'N/A'} ")
        return embed

    async def roblox_api_search(self, username:str, searchid=False):
        usercheck='get-by-username?username=' if searchid is True else ""
        async with self.bot.session.get(f"https://api.roblox.com/users/{usercheck}{username}") as c:
            info=await c.json()
            if 'errorMessage' in info:
                return False
            else:
                return info['Username']

    async def search_by_discord(self, member:discord.Member):
        async with self.bot.session.get(f"https://verify.eryn.io/api/user/{member.id}") as c:
            info=await c.json()
            if info['status'] == "ok":
                return info['robloxUsername']
            else:
                pass
        async with self.bot.session.get(f"https://api.blox.link/v1/user/{member.id}") as c:
            info=await c.json()
            if info['status'] == "ok":
                rcheck=await self.roblox_api_search(info['primaryAccount'], True)
                if rcheck is not False:
                    return rcheck
            else:
                pass
        if member.nick:
            rcheck=await self.roblox_api_search(member.nick)
            if rcheck is not False:
                return rcheck
        rcheck=await self.roblox_api_search(member.name)
        if rcheck is not False:
            return rcheck
        else:
            return None

    async def search_by_roblox(self, ctx:commands.Context, guild:discord.Guild, username:str):
        try:
            member=await commands.MemberConverter().convert(ctx, username)
            return member
        except:
            pass
        guildsearch={}
        for m in guild.members:
            guildsearch[m.name.lower()]=m
            if m.nick is not None:
                guildsearch[m.nick.lower()]=m
        for mem in guildsearch:
            if mem==username:
                return guildsearch[mem]
        return None

    async def build_card_info(self, cardid:str): 
        async with self.bot.session.get(f"https://trello.com/c/{cardid}.json") as t:
            info = await t.json()
        comments=[]
        customfields=[]
        title:str=info['name']
        for comment in info['actions']:
            if comment['type']=='commentCard':
                comments.append(comment['data']['text'])
        url=info['url']
        board=self.bot.boardids[info['idBoard']]
        cardlist=self.bot.lists[info['idList']]
        tmember=None
        if info['idMembers']:
            tmember=info['idMembers'][0]
        lowertitle=title.lower()
        newtitle=None
        if lowertitle.startswith("ex parte "):
            newtitle=lowertitle[9:]
            if ":" in newtitle:
                newtitle=newtitle.split(":")[0]
        else:
            if ":" in lowertitle:
                newtitle=lowertitle.split(":")[0]
        try:
            parsedtime=parser.parse(info['actions'][-1]['date'])
            stringtime=parsedtime.strftime("%m/%d/%Y")
        except:
            stringtime=None
        allinfo={
            'title': title,
            'discord': None,
            'roblox': newtitle,
            'judge': tmember,
            'board': board,
            'list': cardlist,
            'url': url,
            'time': stringtime,
            'comments': comments,
            'customfields': None,
        }
        for action in info['customFieldItems']:
            if action['idCustomField'] == '5dafaa3a6063661f2734cb51':
                allinfo['discord']=action['value']['text'] 
            if 'idValue' in action:
                if action['idValue'] in self.bot.customfields:
                    customfield=self.bot.customfields[action['idValue']]
                    allinfo[customfield[0]]=customfield[1]
                    customfields.append(customfield)
        allinfo['customfields']=customfields
        return allinfo

    async def build_embed(self, cardinfo:dict):
        hascomment=False
        comments="**Card Comments**\n"
        for comment in cardinfo['comments']:
            comments=comments+f"> {comment}\n--\n"
            hascomment=True
        embed=discord.Embed(title=f"Case Info for {cardinfo['title']}", description=f"Board - **{cardinfo['board']}**\nCard List - **{cardinfo['list']}**\n[Card Link]({cardinfo['url']})\n\n{comments if hascomment is True else ''}", timestamp=discord.utils.utcnow(), color=753812)
        for field in cardinfo['customfields']:
            embed.add_field(name=field[0], value=field[1])
        return embed
    
    async def find_expungement_pos(self, carddata:dict):
        async with self.bot.session.get("https://api.trello.com/1/list/5ee0847c0311740ab38f6c3a/cards") as p:
            info=await p.json()
        badcount=0
        pos=None
        first=False
        for i, card in enumerate(info):
            if card['labels']:
                badcount+=1
                continue
            if first is False:
                first=card['shortLink']
            if card['id']==carddata['id']:
                pos=i+1-badcount
        if pos is None:
            return False
        if pos==1:
            saying=False
        else:
            async with self.bot.session.get(f"https://trello.com/c/{first}.json") as t:
                timeinfo=await t.json()
            firstdate=parser.parse(timeinfo['actions'][-1]['date'])
            carddate=parser.parse(carddata['actions'][-1]['date'])
            objdiff=discord.utils.utcnow()-firstdate
            diff=objdiff.days
            if diff==0:
                saying=" Estimated time unavaliable as the expungement has been filed less than24 hours ago."
            else:
                etadate=carddate+datetime.timedelta(days=diff)
                saying=f" The estimated time length until your expungement is heard is `{diff} days`, making the estimated date **{etadate.strftime('%m/%d/%Y')}**."
        return {
            'position': pos,
            'maxposition': i,
            'saying': saying,
        }
    
    async def run_search(self, ctx, search):
        async with self.bot.session.get(f'https://api.trello.com/1/search?modelTypes=cards&query=name:"{search}"&idBoards=593b1c584d118d054065481d') as d:
            dcresults=await d.json()
        async with self.bot.session.get(f'https://api.trello.com/1/search?modelTypes=cards&query=name:"{search}"&idBoards=581f9473930c99e72f209b09') as c:
            csresults=await c.json()
        results=dcresults['cards']+csresults['cards']
        if not results:
            await ctx.send("No search results found, please specify a term in text you wish to search for, or search without an argument.")
            return
        embeds=[]
        badlists=['593b1c65cf948f5ef96fe2bc', '593b1c5e82af460cb51b61c7', '593b20c4a070c27f2048933e', '5cd358266d1c0029533e6880', '613e35722b9a324d83a928db', '5af50745fd4ebab238bbecd5', '5adb8052a04c1efc18f3f649', '5b34ee75a4f7310b788c64a0', '5edc81b737cf0374703505e4', '5ee084d6271f803b0ebea045', '613e1236746ade0675e0fc6b', '615a1aff7fcfe1212ae1a345', '5ee0847d0311740ab38f6c78', '5ee084511193c23f53c595b3', '5ee0843703024b801c52843c']
        addexpunge=False
        for result in results:
            if result['id'] in badlists or result['idList'] in badlists:
                continue
            if result['idList'] not in self.bot.lists or result['closed'] is True:
                continue
            if result['idList']=='5ee0847c0311740ab38f6c3a':
                addexpunge=True
                posinfo=await self.find_expungement_pos(result)
                print(posinfo)
                if posinfo['saying'] is False:
                    saying=""
                else:
                    saying=posinfo['saying']
            info=await self.build_card_info(result['shortLink'])
            embed=await self.build_embed(info)
            embed.set_footer(text=f"Search query: {search}")
            if addexpunge is True:
                embed.description=f"Your expungement is currently **PENDING** and awaiting to be claimed by a Judicial Official. You are are currently number `{posinfo['position']}/{posinfo['maxposition']}` in the Pending Record Expungement Queue.{saying}\n"+embed.description
            embeds.append(embed)
        if not embeds:
            await ctx.send("No search results found!")
            return
        await ButtonPaginate(ctx, embeds, ctx.author)

    @tasks.loop(minutes=2)
    async def checklist(self):
        checktrello=await self.bot.check_trello()
        if checktrello is False:
            return
        async with self.bot.session.get('https://api.trello.com/1/list/6161be61b08f078e2ea15f40/cards') as d:
            dcinfo=await d.json()
        async with self.bot.session.get('https://api.trello.com/1/list/6161be67cc6fb96a709ddd51/cards') as c:
            csinfo=await c.json()
        cards=[]
        for dcard in dcinfo:
            async with self.bot.session.get(f"https://trello.com/c/{dcard['shortLink']}.json") as t:
                cardinfo=await t.json()
            for option in cardinfo['customFieldItems']:
                if 'idValue' in option:
                    if option['idValue'] == '5b3a95425b951686400f76b0':
                        cards.append(dcard['shortLink'])
        for cscard in csinfo:
            cards.append(cscard['shortLink'])
        if self.bot.cardlist is None:
            self.bot.cardlist=cards
            return
        if self.bot.cardlist:
            newcards=[card for card in cards if card not in self.bot.cardlist]
        else:
            newcards=cards
        fakecontext=discord.Object(id=0)
        fakecontext.bot=self.bot
        fakecontext.guild=self.bot.guild
        for c in newcards:
            buildcard=await self.build_card_info(c)
            if buildcard['discord'] is None:
                searchquery=buildcard['roblox']
            else:
                searchquery=buildcard['discord']
            getmem=await self.search_by_roblox(fakecontext, self.bot.guild, searchquery)
            if getmem is None:
                continue
            embed=await self.build_embed(buildcard)
            embed.set_author(name=f"Your case has been ruled on", icon_url=getmem.avatar.url)
            desc=f"`This is an automated message from the Firestone Courts involving a case you've filed. Any bugs or false information in this message should be reported to MrApples#2555`\nOn {buildcard['time']}, you "
            if 'Trial' in buildcard:
                desc=desc+f"petitioned for a `{buildcard['Trial']}`."
            else:
                desc=desc+f"filed a case."
            if buildcard['judge'] is not None:
                desc=desc+f" {self.bot.members[buildcard['judge']]} has ruled on your petition.\n\n"
            else:
                desc=desc+" Your petition has now been ruled on.\n\n"
            embed.description=desc+embed.description
            try:
                await getmem.send(embed=embed)
            except:
                pass
        self.bot.cardlist=cards

    @checklist.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @checklist.error
    async def checklist_error(self, error):
        message = discord.Embed(
            title="Unknown Error", description=f"```python\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```")
        await self.bot.owner.send(embed=message)
        return

    @commands.command(name="search", help="Search for a court case on the District Court of Firestone board or the Case Submission Center board. Will return paginated list of embeds for you to scroll through. You must provide an text argument to search for on the boards. Will return the card link found, the board and list its on, and any applicable custom fields such as status and verdict. If it is a pending expungement, it will also provide its position in line and estimated time of hearing.", brief="Search for a court case")
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    async def search(self, ctx, *, search:str=None):
        checktrello=await self.bot.check_trello()
        if checktrello is False:
            await ctx.send("Trello is currently down, please try again later.")
            return
        if search is None:
            await ctx.send("Provide a search term for me to search for.")
            return
        if len(search)<3:
            await ctx.send("Search term too short.")
            return
        message=await ctx.send("Retriving case info...")
        await self.run_search(ctx, search)
        await message.delete()

    @commands.command(name="caseinfo", help="Search for your own cases in the Case Submission Center or District Court of Firestone. The bot will attempt to connect your Discord account to a Roblox username using your username, discord name, or Rover/Bloxlink connections and search from there. The bot will return a paginated list of embeds containing matches of your Roblox username. Will return the card link found, the board and list its on, and any applicable custom fields such as status and verdict. If it is a pending expungement, it will also provide its position in line and estimated time of hearing.", brief="Get your own court cases")
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    async def caseinfo(self, ctx):
        checktrello=await self.bot.check_trello()
        if checktrello is False:
            await ctx.send("Trello is currently down, please try again later.")
            return
        search=await self.search_by_discord(ctx.author)
        if search is None:
            await ctx.send("I was unable to connect you to a Roblox account! Try changing your nickname to match your Roblox account or verifying with Rover or Bloxlink.")
            return
        message=await ctx.send("Retriving case info...")
        await self.run_search(ctx, search)
        await message.delete()

    @commands.command(name="botinfo", help="Retrives information about the bot, including its latency, uptime, memory usage, and source code info.", brief="Retrives information about the bot")
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def botinfo(self, ctx):
        starttime = time.perf_counter()
        msg=await ctx.send("Retriving bot info...")
        enddtime = time.perf_counter()
        getuptime=discord.utils.utcnow()-self.bot.uptime
        hours, remainder = divmod(int(getuptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        embed=discord.Embed(title="Bot Information", description=f"Utility bot for the Firestone Courts server to inform and assist the public of the Court's functions.\n\n**Uptime** - {days} days, {hours} hours, {minutes} minutes, {seconds} seconds", color=discord.Color.dark_grey(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Discord API Latency", value=f"`{round((enddtime-starttime) * 1000)}ms`")
        embed.add_field(name="Websocket Latency", value=f"`{round(self.bot.latency * 1000)}ms`")
        embed.add_field(name="Lines of Code", value=f"`{self.bot.loc}`")
        embed.add_field(name="Source Language", value="discord.py 2.0.0a")
        embed.add_field(name="Memory Usage", value=f"{round(Process(getpid()).memory_info().rss/1024/1024, 2)} MB")
        embed.add_field(name="CPU Usage", value=f"{Process(getpid()).cpu_percent() / cpu_percent()}%")
        embed.set_footer(text="Created by MrApples#2555, contact me for bugs")
        await msg.delete()
        await ctx.reply(embed=embed)

    @commands.command(name="reload", help="Reloads a cog (updates the changes)", brief="Reloads a cog")
    @commands.is_owner()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.guild)
    async def reload(self, ctx, cog_name=None):
        if cog_name == None:
            await ctx.send("Provide a cog for me to reload!")
            return
        try:
            self.bot.reload_extension(cog_name)
            await ctx.send(f"🔄 {cog_name} successfuly reloaded!")
        except commands.errors.ExtensionNotFound:
            await ctx.send(f"I did not find a cog named {cog_name}.")
            return
        except commands.errors.ExtensionNotLoaded:
            await ctx.send(f"I did not find a cog named {cog_name}.")
            return

    @commands.Cog.listener()    
    async def on_command_error(self, ctx:commands.Context, error:Exception):
        error = getattr(error, 'original', error)
        if isinstance(error, commands.NoPrivateMessage):
            try:
                message = discord.Embed(
                    title="No Private Messages", description=f'{ctx.command} can not be used in Private Messages.')
            except discord.HTTPException:
                pass
        elif isinstance(error, commands.CommandOnCooldown):
            message = discord.Embed(
                title="Cooldown", description=f"This command is on cooldown, try again in `{round(error.retry_after, 1)}` seconds.")
        elif isinstance(error, commands.BadArgument):
            message = await self.command_help_format(ctx.command.name, ctx)
        elif isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, discord.errors.Forbidden):
            message = discord.Embed(
                title="No Permissions", description="I am missing the required permissions to perform this command!")
        else:
            badmsg = discord.Embed(
                title=f"Unknown Error, args: {ctx.args}, kwargs: {ctx.kwargs}", description=f"```python\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```")
            message = discord.Embed(
                title="Unknown Error", description="An unknown error has occured and has been reported to my owner!")
            await self.bot.owner.send(embed=badmsg)
            
        await ctx.send(embed=message)
    
def setup(bot):
    bot.add_cog(CoreCommands(bot))