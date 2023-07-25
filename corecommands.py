from __future__ import annotations
from typing import Union, TYPE_CHECKING
import discord
from discord.ext import tasks, commands
from dpyutils import ButtonPaginator, MoveFlags, CourtHelp, button_confirm
from dateutil import parser
import traceback
import time
from psutil import Process
from os import getpid
from main import on_ready
import config
import random
from datetime import datetime, timedelta
if TYPE_CHECKING:
    from main import CourtsBot
    
DEFAULT_BODY = {"key": config.TRELLOKEY, "token": config.TRELLOTOKEN}

HEADERS = {"Content-Type": "application/json"}


class CoreCommands(commands.Cog):
    def __init__(self, bot):
        self.bot: CourtsBot = bot
        self.checklist.start()

    async def roblox_api_search(
        self, username: str
    ) -> Union[bool, str]:
        result=None
        data={"usernames": [username], "excludeBannedUsers": True}
        response=await self.bot.session.post("https://users.roblox.com/v1/usernames/users", headers=HEADERS, json=data)
        if response.status==200:
            body=await response.json()
            if body["data"]:
                result = body["data"][0]["name"]
            else:
                result = False
        else:
            result = False
        return result

    async def search_by_discord(self, member: discord.Member) -> Union[str, bool]:
        if member.nick:
            rcheck = await self.roblox_api_search(member.nick)
            if rcheck is not False:
                return rcheck
        rcheck = await self.roblox_api_search(member.name)
        return rcheck if rcheck is not False else None

    async def search_by_roblox(
        self, ctx: commands.Context, guild: discord.Guild, username: str
    ) -> Union[str, bool]:
        try:
            member = await commands.MemberConverter().convert(ctx, username)
            return member
        except:
            pass
        guildsearch = {}
        for m in guild.members:
            guildsearch[m.name.lower()] = m
            if m.nick is not None:
                guildsearch[m.nick.lower()] = m
        return next(
            (value for mem, value in guildsearch.items() if mem == username), None
        )

    async def add_to_hecxtro(self, cardinfo: dict) -> None:
        query = {
            "idList": "61882bd6f10b1417f33f0c56",
            "name": f"Ex Parte {cardinfo['name']}",
            "pos": "bottom",
            "urlSource": cardinfo["shortUrl"],
        }
        body = {**DEFAULT_BODY, **query}
        await self.bot.session.post("https://api.trello.com/1/cards", data=body)

    async def build_card_info(self, cardid: str) -> dict:
        info = await self.bot.getreq_json(f"https://trello.com/c/{cardid}.json")
        customfields = []
        title: str = info["name"]
        comments = [
            comment["data"]["text"]
            for comment in info["actions"]
            if comment["type"] == "commentCard"
        ]
        url = info["url"]
        board = self.bot.boardids[info["idBoard"]]
        cardlist = self.bot.lists[info["idList"]]
        tmember = info["idMembers"][0] if info["idMembers"] else None
        lowertitle = title.lower()
        newtitle = None
        if lowertitle.startswith("ex parte "):
            newtitle = lowertitle[9:]
            if ":" in newtitle:
                newtitle = newtitle.split(":")[0]
        elif ":" in lowertitle:
            newtitle = lowertitle.split(":")[0]
        try:
            parsedtime = parser.parse(info["actions"][-1]["date"])
            stringtime = parsedtime.strftime("%m/%d/%Y")
        except:
            stringtime = None
        allinfo = {
            "title": title,
            "discord": None,
            "roblox": newtitle,
            "judge": tmember,
            "board": board,
            "list": cardlist,
            "url": url,
            "time": stringtime,
            "comments": comments,
            "customfields": None,
        }
        for action in info["customFieldItems"]:
            if action["idCustomField"] == "5dafaa3a6063661f2734cb51":
                allinfo["discord"] = action["value"]["text"]
            if "idValue" in action and action["idValue"] in self.bot.customfields:
                customfield = self.bot.customfields[action["idValue"]]
                allinfo[customfield[0]] = customfield[1]
                customfields.append(customfield)
        allinfo["customfields"] = customfields
        return allinfo

    async def build_embed(self, cardinfo: dict) -> discord.Embed:
        hascomment = False
        comments = "**Card Comments**\n"
        for comment in cardinfo["comments"]:
            comments += f"> {comment}\n--\n"
            hascomment = True
        embed = discord.Embed(
            title=f"Case Info for {cardinfo['title']}",
            description=f'Board - **{cardinfo["board"]}**\nCard List - **{cardinfo["list"]}**\n[Card Link]({cardinfo["url"]})\n\n{comments if hascomment else ""}',
            timestamp=discord.utils.utcnow(),
            color=753812,
        )

        for field in cardinfo["customfields"]:
            embed.add_field(name=field[0], value=field[1])
        return embed

    async def format_expungement(self, cardinfo: dict, judge: str) -> None:
        query = {
            "name": f"Ex Parte {cardinfo['name']}",
            "idMembers": self.bot.memids[judge],
            "idBoard": "593b1c584d118d054065481d",
            "idList": self.bot.judgelists[judge],
            "pos": "bottom",
        }
        body = {**DEFAULT_BODY, **query}
        await self.bot.session.put(
            f"https://api.trello.com/1/cards/{cardinfo['id']}", data=body
        )

    async def add_expunge_fields(self, cardinfo: dict) -> None:
        statusquery = {"idValue": "5c3bcd0f80f20614a4c72098"}
        typequery = {"idValue": "5b3a95425b951686400f76b0"}
        casenumquery = {
            "value": {
                "text": f"C-{datetime.now().strftime('%m%d%y')}-{random.randint(100, 999)}"
            }
        }
        allqueries = {
            "5c3bcd0f80f20614a4c72093": statusquery,
            "5b06d74758c55f9759d896df": typequery,
            "5b37afa9bd79cab1decc0eb4": casenumquery,
        }
        for q, value in allqueries.items():
            dofields = await self.bot.session.put(
                f"https://api.trello.com/1/card/{cardinfo['id']}/customField/{q}/item",
                headers=HEADERS,
                json={**DEFAULT_BODY, **value},
            )

    async def expungify(self, cardinfo: dict, judge: str, hecxtro=False) -> None:
        await self.format_expungement(cardinfo, judge)
        await self.add_expunge_fields(cardinfo)
        if hecxtro is True:
            await self.add_to_hecxtro(cardinfo)

    async def find_expungement_pos(self, carddata: dict) -> Union[bool, dict]:
        info = await self.bot.getreq_json("https://api.trello.com/1/list/5ee0847c0311740ab38f6c3a/cards")
        print(info)
        badcount = 0
        pos = None
        first = False
        for i, card in enumerate(info):
            if not first:
                first = card["shortLink"]
            if card["id"] == carddata["id"]:
                pos = i + 1
        if pos is None:
            saying = False
        elif pos == 1:
            saying = False
        else:
            timeinfo = await self.bot.getreq_json(f"https://trello.com/c/{first}.json")
            currentinfo = await self.bot.getreq_json(f"https://trello.com/c/{carddata['shortLink']}.json")
            firstdate = parser.parse(timeinfo["actions"][-1]["date"])
            carddate = parser.parse(currentinfo["actions"][-1]["date"])
            objdiff = discord.utils.utcnow() - firstdate
            diff = objdiff.days
            if diff == 0:
                saying = " Estimated time unavaliable as the expungement has been filed less than 24 hours ago."
            else:
                etadate = (
                    carddate
                    + timedelta(days=diff)
                    + timedelta(days=15)
                )
                etadelta = etadate - discord.utils.utcnow()
                saying = f" It is likely that your expungement will be processed within approximately **{etadelta.days} days** (before __{etadate.strftime('%m/%d/%Y')}__)"
        return {
            "position": pos,
            "maxposition": i,
            "saying": saying,
        }

    async def run_search(self, ctx, search) -> bool:
        dcresults = await self.bot.getreq_json(f'https://api.trello.com/1/search?modelTypes=cards&query=name:"{search}"&idBoards=593b1c584d118d054065481d')
        csresults = await self.bot.getreq_json(f'https://api.trello.com/1/search?modelTypes=cards&query=name:"{search}"&idBoards=581f9473930c99e72f209b09')
        results = dcresults["cards"] + csresults["cards"]
        if not results:
            return False
        embeds = []
        badlists = [
            "593b1c65cf948f5ef96fe2bc",
            "593b1c5e82af460cb51b61c7",
            "593b20c4a070c27f2048933e",
            "5cd358266d1c0029533e6880",
            "613e35722b9a324d83a928db",
            "5af50745fd4ebab238bbecd5",
            "5adb8052a04c1efc18f3f649",
            "5b34ee75a4f7310b788c64a0",
            "5edc81b737cf0374703505e4",
            "5ee084d6271f803b0ebea045",
            "613e1236746ade0675e0fc6b",
            "615a1aff7fcfe1212ae1a345",
            "5ee0847d0311740ab38f6c78",
            "5ee084511193c23f53c595b3",
            "5ee0843703024b801c52843c",
        ]
        addexpunge = False
        for result in results:
            if result["id"] in badlists or result["idList"] in badlists:
                continue
            if result["idList"] not in self.bot.lists or result["closed"] is True:
                continue
            if result["idList"] == "5ee0847c0311740ab38f6c3a":
                addexpunge = True
                posinfo = await self.find_expungement_pos(result)
                saying = "" if posinfo["saying"] is False else posinfo["saying"]
            info = await self.build_card_info(result["shortLink"])
            embed = await self.build_embed(info)
            embed.set_footer(text=f"Search query: {search}")
            if addexpunge:
                embed.description = (
                    f"This expungement is currently **PENDING** and awaiting to be claimed by a Judicial Official. The expungement is currently number `{posinfo['position']}/{posinfo['maxposition']}` in the Pending Record Expungement Queue.{saying}\n"
                    + embed.description
                )
            embeds.append(embed)
        if not embeds:
            return False
        await ButtonPaginator.ButtonPaginate(ctx, embeds)

    @tasks.loop(minutes=2)
    async def checklist(self):
        checktrello = await self.bot.check_trello()
        if checktrello is False:
            return
        dcinfo = await self.bot.getreq_json("https://api.trello.com/1/list/614cc2a13fd8132ec09ca24c/cards")
        csinfo = await self.bot.getreq_json("https://api.trello.com/1/list/614e0d3654a68e12239f6c1b/cards")
        cards = []
        for dcard in dcinfo:
            cardinfo = await self.bot.getreq_json("https://trello.com/c/{dcard['shortLink']}.json")
            for option in cardinfo["customFieldItems"]:
                if (
                    "idValue" in option
                    and option["idValue"] == "5b3a95425b951686400f76b0"
                ):
                    cards.append(dcard["shortLink"])
        for cscard in csinfo:
            cards.append(cscard["shortLink"])
        if self.bot.cardlist is None:
            self.bot.cardlist = cards
            return
        if self.bot.cardlist:
            newcards = [
                card for card in cards if card not in self.bot.cardlist]
        else:
            newcards = cards
        fakecontext = discord.Object(id=0)
        fakecontext.bot = self.bot
        fakecontext.guild = self.bot.guild
        for c in newcards:
            buildcard = await self.build_card_info(c)
            if buildcard["discord"] is None:
                searchquery = buildcard["roblox"]
            else:
                searchquery = buildcard["discord"]
            getmem = await self.search_by_roblox(
                fakecontext, self.bot.guild, searchquery
            )
            if getmem is None:
                continue
            embed = await self.build_embed(buildcard)
            embed.set_author(
                name="Your case has been ruled on",
                icon_url=getmem.display_avatar.url,
            )

            desc = f"`This is an automated message from the Firestone Courts involving a case you've filed. Any bugs or false information in this message should be reported to MrApples#2555`\nOn {buildcard['time']}, you "
            if "Trial" in buildcard:
                desc = desc + f"petitioned for a `{buildcard['Trial']}`."
            else:
                desc = desc + "filed a case."
            if buildcard["judge"] is not None:
                desc = (
                    desc
                    + f" {self.bot.members[buildcard['judge']]} has ruled on your petition.\n\n"
                )
            else:
                desc = desc + " Your petition has now been ruled on.\n\n"
            embed.description = desc + embed.description
            try:
                await getmem.send(embed=embed)
            except:
                pass
        self.bot.cardlist = cards

    @checklist.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @checklist.error
    async def checklist_error(self, error):
        message = discord.Embed(
            title="Unknown Error",
            description=f"```python\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```",
        )
        await self.bot.owner.send(embed=message)
        return

    @commands.command(
        name="search",
        help="Search for a court case on the District Court of Firestone board or the Case Submission Center board. Will return paginated list of embeds for you to scroll through. You must provide an text argument to search for on the boards. Will return the card link found, the board and list its on, and any applicable custom fields such as status and verdict. If it is a pending expungement, it will also provide its position in line and estimated time of hearing.",
        brief="Search for a court case",
    )
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    async def search(self, ctx: commands.Context, *, query: str = None):
        checktrello = await self.bot.check_trello()
        if checktrello is False:
            await ctx.reply("Trello is currently down, please try again later.")
            return
        if query is None:
            await ctx.reply("Provide a search term for me to search for.")
            return
        if len(query) < 3:
            await ctx.reply("Search term too short.")
            return
        message: discord.Message = await ctx.reply("Retriving case info...")
        getsearch = await self.run_search(ctx, query)
        await message.delete()
        if getsearch is False:
            await ctx.reply("No search results were found with your search query.")
            return

    @commands.command(
        name="caseinfo",
        help="Search for your own cases in the Case Submission Center or District Court of Firestone. The bot will attempt to connect your Discord account to a Roblox username using your username, discord name, or Rover/Bloxlink connections and search from there. The bot will return a paginated list of embeds containing matches of your Roblox username. Will return the card link found, the board and list its on, and any applicable custom fields such as status and verdict. If it is a pending expungement, it will also provide its position in line and estimated time of hearing.",
        brief="Get your own court cases",
    )
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    async def caseinfo(self, ctx: commands.Context):
        checktrello = await self.bot.check_trello()
        checkroblox = await self.bot.check_roblox()
        if checktrello is False:
            await ctx.reply("Trello is currently down, please try again later.")
            return
        if checkroblox is False:
            await ctx.reply(
                "ROBLOX is currently down, therefore we can't connect you to a ROBLOX account. Please use the search command for now."
            )
            return
        #try:
        search = await self.search_by_discord(ctx.author)
        #except:
        #await ctx.reply(
        "ROBLOX is currently down, therefore we cannot cannot connect you to a ROBLOX account. Try using the search command with your own query"
        #)
        #return
        if search is None:
            await ctx.reply(
                "I was unable to connect you to a Roblox account! Try changing your nickname to match your Roblox account, verifying with Rover or Bloxlink, or using the `?search`."
            )
            return
        message = await ctx.reply("Retriving case info...")
        getsearch = await self.run_search(ctx, search)
        await message.delete()
        if getsearch is False:
            await ctx.reply(
                f"No search results found using search query __{search}__. If this isn't your ROBLOX username, this may because you verified with a different account on Rover or Bloxlink, or your Discord name/nickname isn't your ROBLOX username. Try using the search command and provide your own query."
            )
            return

    @commands.command(
        name="botinfo",
        help="Retrives information about the bot, including its latency, uptime, memory usage, and source code info.",
        brief="Retrives information about the bot",
    )
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.user)
    async def botinfo(self, ctx: commands.Context):
        starttime = time.perf_counter()
        msg = await ctx.reply("Retriving bot info...")
        enddtime = time.perf_counter()
        getuptime = discord.utils.utcnow() - self.bot.uptime
        hours, remainder = divmod(int(getuptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        embed = discord.Embed(
            title="Bot Information",
            description=f"Utility bot for the Firestone Courts server to inform and assist the public of the Court's functions.\n\n**Uptime** - {days} days, {hours} hours, {minutes} minutes, {seconds} seconds",
            color=discord.Color.dark_grey(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(
            name="Discord API Latency",
            value=f"`{round((enddtime-starttime) * 1000)}ms`",
        )
        embed.add_field(
            name="Websocket Latency", value=f"`{round(self.bot.latency * 1000)}ms`"
        )
        embed.add_field(name="Lines of Code", value=f"`{self.bot.loc}`")
        embed.add_field(name="Source Language", value="discord.py 2.0.0a")
        embed.add_field(
            name="Memory Usage",
            value=f"{round(Process(getpid()).memory_info().rss/1024/1024, 2)} MB",
        )
        embed.add_field(name="CPU Usage",
                        value=f"{Process(getpid()).cpu_percent()}%")
        embed.set_footer(text="Created by MrApples#2555, contact me for bugs")
        await msg.delete()
        await ctx.reply(embed=embed)

    @commands.command(
        name="reload", help="Reloads a cog (updates the changes)", brief="Reloads a cog"
    )
    @commands.is_owner()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.guild)
    async def reload(self, ctx: commands.Context, cog_name=None):
        if cog_name is None:
            await ctx.reply("Provide a cog for me to reload!")
            return
        try:
            self.bot.reload_extension(cog_name)
            await ctx.reply(f"🔄 {cog_name} successfuly reloaded!")
        except commands.errors.ExtensionNotFound:
            await ctx.reply(f"I did not find a cog named {cog_name}.")
            return
        except commands.errors.ExtensionNotLoaded:
            await ctx.reply(f"I did not find a cog named {cog_name}.")
            return

    @commands.command(
        name="expungify",
        help="Formats cards ready for expungement processing on the case submission board including adding custom fields, adding the members, and changing the name. You must move the cards to the `Prepare for Expungement` list before you run this command. You must specify which docket you want it moved to using a flag in the following format: `--judge <judge name>`. For example `!expungify --judge Hecxtro` will format cards for expungement and move it to Hecxtro's docket.",
        brief="Prepares a batch of cards on Trello for expungement.",
    )
    @commands.has_any_role(
        "District Court Judge", "Associate Justice", "Chief Justice", "Clerk"
    )
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.guild)
    async def expungify_cmd(self, ctx: commands.Context, *, flags: MoveFlags):
        cards = await self.bot.getreq_json("https://api.trello.com/1/list/61a82ae6b3a2477b5cd8e8c0/cards")
        if not cards:
            await ctx.send(
                "There are no cards to expungify, make sure you moved all cards you want to process into the `Prepare For Expungement` list before running this command."
            )
            return
        judgename = flags.judge.lower()
        if judgename not in self.bot.judgelists:
            await ctx.send(
                "Improper flag format. Run the help command and look for this command to find proper usage of the flag."
            )
            return
        numcards = len(cards)
        confirm, message = await button_confirm(
            ctx.author,
            ctx.channel,
            f"Are you sure you wish to process `{numcards}` expungements on Trello?",
        )
        if confirm is False or confirm is None:
            await message.edit("Confirmation cancelled", view=None)
            return
        await message.edit(f"Formatting {numcards} expungements...", view=None)
        for card in cards:
            await self.expungify(card, judgename, judgename == "hecxtro")
        await message.edit("Expungements formatted.")

    @commands.command(
        name="reloadlists",
        help="Reloads the bots list data",
        brief="Reloads the bots list data",
    )
    @commands.is_owner()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.guild)
    async def reloadlists(self, ctx: commands.Context):
        await self.bot.reload_lists()
        await ctx.reply("Trello list data successfully reloaded.")

    @commands.command(
        name="reloadready",
        help="Reloads the bots data by recalling its `on_ready` function",
        brief="Reloads the bots data",
    )
    @commands.is_owner()
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.guild)
    async def reloadready(self, ctx: commands.Context):
        await on_ready()
        await ctx.reply("Bot data reloaded.")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        error = getattr(error, "original", error)
        if isinstance(error, commands.NoPrivateMessage):
            try:
                message = discord.Embed(
                    title="No Private Messages",
                    description=f"{ctx.command} can not be used in Private Messages.",
                )
            except discord.HTTPException:
                pass
        elif isinstance(error, commands.CommandOnCooldown):
            message = discord.Embed(
                title="Cooldown",
                description=f"This command is on cooldown, try again in `{round(error.retry_after, 1)}` seconds.",
            )
        elif isinstance(
            error, (commands.BadArgument, commands.MissingRequiredArgument)
        ):
            message = await CourtHelp().send_command_help(
                ctx.command, fake=True, context=ctx
            )
        elif isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
            return
        elif isinstance(error, discord.errors.Forbidden):
            message = discord.Embed(
                title="No Permissions",
                description="I am missing the required permissions to perform this command!",
            )
        elif isinstance(error, (commands.NotOwner, commands.MissingAnyRole)):
            message = discord.Embed(
                title="Missing Permissions",
                description="You are missing the required permissions to run this command",
            )
        else:
            badmsg = discord.Embed(
                title=f"Unknown Error, args: {ctx.args}, kwargs: {ctx.kwargs}",
                description=f"```python\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```",
            )
            message = discord.Embed(
                title="Unknown Error",
                description="An unknown error has occured and has been reported to my owner!",
            )
            await self.bot.owner.send(embed=badmsg)

        await ctx.reply(embed=message)


def setup(bot: CourtsBot):
    bot.add_cog(CoreCommands(bot))
