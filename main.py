import discord
from discord.ext import commands, tasks
import aiohttp
import config
from dpyutils import CourtHelp, WarrantRequestInit
import pathlib
from typing import List
import asqlite
class CourtsBot(commands.Bot):
    def __init__(self):
        super().__init__(
            intents=discord.Intents.all(),
            command_prefix=commands.when_mentioned_or("?"),
            case_insensitive=True,
            help_command=CourtHelp(),
        )
        self.uptime = discord.utils.utcnow()
        self.customfields = {}
        self.lists = {}
        self.boardids = {
            "593b1c584d118d054065481d": "District Court of Firestone",
            "581f9473930c99e72f209b09": "Firestone Courts Case Submission Center",
        }
        self.members = {}
        self.judgelists = {}
        self.cardlist = None
        self.guild = None
        self.owner = None
        self.loc = None
        self.memids = {}
        self.cfitems = [
            "5c3bcd0f80f20614a4c72093",
            "5b08b5face269325c8ed581d",
            "5b06d74758c55f9759d896df",
            "5b06d1c81e3ecc5e2f288da7",
            "5bca6f3c24afea5d2b007136",
            "5c54684b92c5f91774896b08",
        ]
        self.db_pool : asqlite.Pool = None
        self.warrant_req_message = None
        self.warrant_req_channel = None

    async def check_trello(self):
        async with self.session.get(
            "https://api.trello.com/1/boards/593b1c584d118d054065481d"
        ) as c:
            return c.status == 200

    async def check_roblox(self):
        async with self.session.get(
            "https://users.roblox.com/v1/users/1143706094"
        ) as r:
            if r.status == 200:
                return True

            try:
                await r.json()
                return True
            except aiohttp.ContentTypeError:
                return False

    async def reload_lists(self):
        for board in self.boardids:
            async with self.session.get(
                f"https://api.trello.com/1/boards/{board}/lists"
            ) as b:
                info = await b.json()
            for list in info:
                self.lists[list["id"]] = list["name"]
    
    async def load_db(self):
        self.db_pool = await asqlite.create_pool('records.db', size=20)

    def run_bot(self):
        p = pathlib.Path("./")
        count = 0
        for f in p.rglob("*.py"):
            if str(f).startswith("config") or str(f).startswith("env"):
                continue
            with f.open(encoding="utf8") as of:
                for _ in of.readlines():
                    count += 1
        self.loc = count
        self.run(config.TOKEN)

    async def getreq_json(self, url: str):
        async with self.session.get(url) as i:
            info = await i.json()
        return info
    
    async def setup_hook(self):
        await self.load_extension("corecommands")
        await self.load_db()
        async with await self.db_pool.acquire() as cnc:
            msg_cursor = await cnc.fetchone("SELECT * FROM request_message;")
            self.warrant_req_message = dict(msg_cursor)['messageid']
            chnl_cursor = await cnc.fetchone("SELECT channelid FROM request_channel;")
            self.warrant_req_channel = dict(chnl_cursor)['channelid']
        req_channel = await self.fetch_channel(int(self.warrant_req_channel))
        self.add_view(WarrantRequestInit(self.db_pool, req_channel), message_id=self.warrant_req_message)
        self.session = aiohttp.ClientSession(loop=self.loop)
    
    async def close(self):
        await self.db_pool.close()
        await super().close()

bot = CourtsBot()


@bot.event
async def on_ready():
    bot.guild = bot.get_guild(322924318545805312)
    bot.owner = bot.get_user(474744664449089556)
    checktrello = await bot.check_trello()
    if checktrello is False:
        await bot.owner.send("trello is down auto shutdown")
        print("trello is down")
        await bot.close()
    for item in bot.cfitems:
        info = await bot.getreq_json(f"https://api.trello.com/1/customFields/{item}")
        for option in info["options"]:
            bot.customfields[option["id"]] = [
                info["name"], option["value"]["text"]]
    await bot.reload_lists()
    cinfo = await bot.getreq_json("https://api.trello.com/1/list/593b1c5e82af460cb51b61c7/cards")
    for member in cinfo:
        memname: str = member["name"]
        if memname == "---":
            continue
        elif "5f08e10710f2927fbd85a4a1" in member["idLabels"]:
            continue
        getname = memname.split(" ")
        bot.memids[getname[-1].lower()] = [member["idMembers"][0]]
        bot.members[member["idMembers"][0]] = getname[-1]
    lists = await bot.getreq_json("https://api.trello.com/1/boards/593b1c584d118d054065481d/lists")
    for ls in lists:
        name: str = ls["name"]
        if " " not in name:
            continue
        splitname = name.split(" ")[-1].lower()
        if splitname in bot.memids:
            bot.judgelists[splitname] = ls["id"]
    print("bot is ready")


@bot.check
async def block_dms(ctx: commands.Context):
    return ctx.guild is not None

if __name__ == "__main__":
    bot.run_bot()
