import discord
from discord.ext import tasks, commands

class CaseCheck(commands.Cog):
    def __init__(self, bot):
        self.bot=bot

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

    async def search_by_roblox(self, ctx:commands.Context, guild:discord.Guild, username:str):
        try:
            member=commands.MemberConverter.convert(ctx, username)
            return member
        except:
            pass
        cursor=await self.bot.db.cursor()
        getuser=await cursor.execute("SELECT member FROM usernames WHERE username = ?", username)
        if getuser is not None:
            for row in getuser:
                return guild.get_member(row[0])
        guildsearch={}
        for m in guild.members:
            guildsearch[m.name]=m
            guildsearch[m.nick]=m
        for mem in guildsearch:
            if mem==username:
                return guildsearch[mem]
        return False

    async def build_card_info(self, cardid:str): 
        async with self.bot.session.get(f"https://trello.com/c/{cardid}.json") as t:
            info = await t.json()
        comments=[]
        customfields=[]
        title=info['name']
        nametag=None
        for comment in info['actions']:
            if comment['type']=='commentCard':
                comments.append(comment['data']['text'])
        for action in info['customFieldItems']:
            if action['id'] == '6160b5e0dd8abf1dfa361802':
                nametag=action['id']['value']['text'] 
            if action['id'] in self.bot.customfields:
                customfields.append(self.bot.customfields[action])
        url=info['url']
        board=self.bot.boardids[info['idBoard']]
        cardlist=self.board.lists[info['idList']]
        allinfo={
            'title': title,
            'discord': nametag,
            'board': board,
            'list': cardlist,
            'url': url,
            'commands': comments,
            'customfields': customfields,
        }
        return allinfo

    @tasks.loop(seconds=15)
    async def checklist(self):
        async with self.bot.session.get('https://api.trello.com/1/list/614cc2a13fd8132ec09ca24c/cards') as d:
            dcinfo=await d.json()
        async with self.bot.session.get('https://api.trello.com/1/list/614e0d3654a68e12239f6c1b/cards') as c:
            csinfo=await c.json()
        cards=[]
        for dcard in dcinfo:
            cards.append(dcard['id'])
        for cscard in csinfo:
            cards.append(cscard['id'])
        if self.bot.cards is None:
            self.bot.cardlist=cards
            return
        newcards=[card for card in cards if card not in self.bot.cardlist]
        