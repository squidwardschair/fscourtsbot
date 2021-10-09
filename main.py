import discord
from discord.ext import commands, tasks
import aiohttp
import config
import datetime
import os
import asqlite

class CourtsBot(commands.Bot):
    def __init__(self):
        super().__init__(intents=discord.Intents.all(), command_prefix=commands.when_mentioned_or("c!"), case_insensitive=True)
        self.uptime=discord.utils.utcnow()
        self.db=None
        self.customfields={}
        self.lists={}
        self.boardids={"593b1c584d118d054065481d": "District Court of Firestone", "581f9473930c99e72f209b09": "Firestone Courts Case Submission Center"}
        self.cardlist=[]

    async def close(self):
        await self.session.close()
        await super().close()

    async def on_connect(self):
        self.session=aiohttp.ClientSession(loop=self.loop)
        cfitems=['5c3bcd0f80f20614a4c72093', '5b08b5face269325c8ed581d', '5b06d74758c55f9759d896df', '5b06d1c81e3ecc5e2f288da7', '5bca6f3c24afea5d2b007136', '5c54684b92c5f91774896b08']
        for item in cfitems:
            async with self.bot.session.get(f"https://api.trello.com/1/customFields/{item}") as i:
                info=await i.json()
            for option in info['options']:
                self.customfields[option['id']] = [info['name'], option['value']['text']]
        for board in self.boardids:
            async with self.bot.session.get(f"https://api.trello.com/1/boards/{board}/lists") as b:
                info=await b.json()
            for list in info:
                self.lists[list['id']]=list['name']

    async def run_bot(self):
        self.db=await asqlite.connect("robloxdiscord.db")
        for extension in os.listdir():
            cog=extension[:-3]
            self.load_extension(cog)
        self.run(config.TOKEN)

bot=CourtsBot()

@bot.event
async def on_ready():
    print("bot is ready")

bot.run_bot()