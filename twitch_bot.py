import os
import random
import ssl
import aiohttp
import asyncio
from riot_client import RiotClient
from lolpros_api import LolprosApi
from db import Database, Account

ADMIN_USERS = ["reptile9lol", "gcorebyte", "k1mbo9lol"]

NOT_IN_GAME = "Reptile is currently not in game"

def is_admin(user: str):
    # This should probably check if the user is a mod too
    return user.lower().strip() in ADMIN_USERS


class TwitchBot:
    def __init__(self):
        self.reader = None
        self.writer = None
        self.riot = None
        self.lolpros = None
        self.db = Database()
        self.count = 1
        self.previous_message = ""

    async def connect(self):
        # https://docs.python.org/3/library/ssl.html#ssl-security
        ssl_context = ssl.create_default_context()
        reader, writer = await asyncio.open_connection(
            os.getenv("TWITCH_SERVER"),
            int(os.getenv("TWITCH_PORT")),
            ssl=ssl_context
        )
        self.reader = reader
        self.writer = writer

        self._send(f"PASS {os.getenv('TWITCH_TOKEN')}")
        self._send(f"NICK {os.getenv('TWITCH_NICK')}")
        self._send(f"JOIN {os.getenv('TWITCH_CHANNEL')}")
        # self._send(f"CAP REQ :twitch.tv/tags")
        print("[Bot] Connected to Twitch")

    def _send(self, message, log=True):
        if log:
            # Debugging purposes
            print(f"[SEND] {message}")
        self.writer.write(f"{message}\r\n".encode())

    def send(self, user, twitch_channel, message, reply_id = None):
        if reply_id:
            self._send(f"@reply-parent-msg-id={reply_id} PRIVMSG {twitch_channel} :{message}")
        else:
            self._send(f"PRIVMSG {twitch_channel} :@{user}, {message}")

    def send_without_mention(self, twitch_channel, message):
        self._send(f"PRIVMSG {twitch_channel} :{message}")

    async def listen(self):
        async with aiohttp.ClientSession() as session:
            self.riot = RiotClient(session)
            self.lolpros = LolprosApi(session)
            while True:
                line = await self.reader.readline()
                if not line:
                    break

                decoded = line.decode().strip()
                # DEBUG
                # print(f"[RECV] {decoded}")

                if decoded.startswith("PING"):
                    self._send("PONG :tmi.twitch.tv", log=False)
                elif "PRIVMSG" in decoded:
                    await self.handle_command(decoded)

    # I don't like how I handle this currently. This method is not extendable.
    # Probably best to add a self.commands = {} type object
    # Where the key is the string and the value is the function to run
    async def handle_command(self, message):
        user = message.split("!", 1)[0][1:]
        content: str = message.split(":", 2)[2]
        if user.lower() == "nightbot" or user.lower() == "botile9lol":
            return
        # Processing
        content = content.removesuffix("  󠀀") # 7tv send twice hack
        content = content.removesuffix(" 󠀀")
        content = content.strip()
        normalized_content = content.lower()

        # FIXME
        if normalized_content.startswith("!runes"):
            result = await self.runes()
            self.send(user, os.getenv('TWITCH_CHANNEL'), result)
        elif normalized_content.startswith("!pros"):
            result = await self.pros()
            if result is None:
                result = NOT_IN_GAME
            self.send(user, os.getenv('TWITCH_CHANNEL'), result)
        elif normalized_content.startswith("!rank"):
            result = await self.rank()
            self.send(user, os.getenv('TWITCH_CHANNEL'), result)
        elif not normalized_content.startswith("!") and "skin" in normalized_content and ("what" in normalized_content or "which" in normalized_content):
            current_champion = await self.get_current_champion()
            if current_champion == "Zeri":
                self.send(user, os.getenv('TWITCH_CHANNEL'), "high noon zeri, custom skin from https://runeforge.dev/mods/f03862cc-4324-4f18-bd64-df0c376785cb")
            elif current_champion == "Vayne":
                self.send(user, os.getenv('TWITCH_CHANNEL'), "kda all out vayne, custom skin from https://www.runeforge.io/post/k-da-all-out-vayne")
            elif current_champion == "Xayah":
                self.send(user, os.getenv('TWITCH_CHANNEL'), "winterblessed xayah, custom skin from https://www.runeforge.io/post/winterblessed-xayah")
        elif not normalized_content.startswith("!") and "zeri" in normalized_content and "skin" in normalized_content:
            self.send(user, os.getenv('TWITCH_CHANNEL'), "high noon zeri, custom skin from https://runeforge.dev/mods/f03862cc-4324-4f18-bd64-df0c376785cb")
        elif not normalized_content.startswith("!") and "vayne" in normalized_content and "skin" in normalized_content:
            self.send(user, os.getenv('TWITCH_CHANNEL'), "kda all out vayne, custom skin from https://www.runeforge.io/post/k-da-all-out-vayne")
        #elif not normalized_content.startswith("!") and "jhin" in normalized_content and "skin" in normalized_content:
            #self.send(user, os.getenv('TWITCH_CHANNEL'), "spirit blossom jhin, custom skin from https://runeforge.dev/mods/16e6bd39-df9e-4e02-b2d1-71a1b814eb94")
        elif not normalized_content.startswith("!") and "xayah" in normalized_content and "skin" in normalized_content:
            self.send(user, os.getenv('TWITCH_CHANNEL'), "winterblessed xayah, custom skin from https://www.runeforge.io/post/winterblessed-xayah")
        elif not normalized_content.startswith("!") and "delay" in normalized_content:
            self.send_without_mention(os.getenv('TWITCH_CHANNEL'), "!delay")
        elif not normalized_content.startswith("!") and ("hob" in normalized_content or "hail of blades" in normalized_content) and not "ad" in normalized_content:
            text = "LT is really slow to stack doesn't give too much value when stacked. Because Zeri turns AS past 1.5 into AD, with HOB you get a big burst to AD immediately in fights."
            if "zeri" in normalized_content:
                return self.send(user, os.getenv('TWITCH_CHANNEL'), text)
            result = await self.is_champion("Zeri")
            if result:
                self.send(user, os.getenv('TWITCH_CHANNEL'), text)
        # elif "@botile9lol" in normalized_content and "sentient" in normalized_content:
        #    self.send(user, os.getenv('TWITCH_CHANNEL'), "yea bro im sentient")
        # elif (not normalized_content.startswith("!")) and "@botile9" in normalized_content and ("can" in normalized_content or "would" in normalized_content or "do" in normalized_content or "is" in normalized_content or "are" in normalized_content or "will"):
        #    self.send(user, os.getenv('TWITCH_CHANNEL'), random.choice(["yea", "nah", "maybe"]))
        # elif not normalized_content.startswith("!") and "@botile9" in normalized_content and "hi" in normalized_content:
        #    self.send(user, os.getenv('TWITCH_CHANNEL'), "hi")
        # elif not normalized_content.startswith("!") and "@botile9" in normalized_content and "bye" in normalized_content:
        #    self.send(user, os.getenv('TWITCH_CHANNEL'), "bye")
        elif is_admin(user) and normalized_content.startswith("!"):
            if normalized_content.startswith("!add"):
                name, tag = normalized_content.removeprefix("!add ").split("#")
                result = await self.add_account(name, tag)
                self.send(user, os.getenv('TWITCH_CHANNEL'), result)
            elif normalized_content.startswith("!delete"):
                name, tag = normalized_content.removeprefix("!delete ").split("#")
                result = await self.delete_account(name, tag)
                self.send(user, os.getenv('TWITCH_CHANNEL'), result)
            elif normalized_content.startswith("!accounts"):
                result = await self.accounts()
                self.send(user, os.getenv('TWITCH_CHANNEL'), result)
            elif normalized_content.startswith("!restart"):
                self.send(user, os.getenv('TWITCH_CHANNEL'), "Restarting...")
                exit(0)
            elif normalized_content.startswith("!s "):
                self.send_without_mention(os.getenv('TWITCH_CHANNEL'), content.removeprefix("!s "))
        else:
            # Hack - join emote walls
            if content.strip() == self.previous_message:
                self.count += 1
            else:
                self.count = 1
                if content.startswith("!"):
                    self.previous_message = ""
                else:
                    self.previous_message = content.strip()
        if self.count == 4:
            self.send_without_mention(os.getenv('TWITCH_CHANNEL'), self.previous_message)

    # Move to own module
    async def runes(self):
        accounts = self.db.get_all_accounts()
        if len(accounts) == 0:
            return "No accounts configured"
        for account in accounts:
            try:
                result = await self.riot.get_runes_for(account)
                if result is not None:
                    return result
            except Exception as e:
                # Something went really wrong, log it and also give the error in twitch chat
                # Probably best to remove it from twitch chat later
                print(f"[Bot] Error: {e}")
                return f"erm what did u do: {e}"
        return NOT_IN_GAME

    # Move these to their own module and add them to self.commands
    async def add_account(self, name: str, tag: str):
        account = self.db.get_account_by_name_and_tag(name, tag)
        if account:
            return f"Account {name}#{tag} already exists"
        account = Account(name=name, tag=tag)
        account.save()
        return f"Added {name}#{tag} to the database"

    async def delete_account(self, name: str, tag: str):
        account = self.db.get_account_by_name_and_tag(name, tag)
        if account:
            account.delete()
            return f"Deleted {name}#{tag} from the database"
        return f"Account {name}#{tag} not found"

    async def accounts(self):
        accounts = self.db.get_all_accounts()
        if len(accounts) == 0:
            return "No accounts configured"
        full_names = [account.full_name() for account in accounts]
        return ", ".join(full_names)

    async def pros(self):
        accounts = self.db.get_all_accounts()
        if len(accounts) == 0:
            return "No accounts configured"
        for acc in accounts:
            try:
                result = await self.lolpros.get_all_pro_names(acc)
                if result is not None:
                    return result
            except Exception as e:
                # Something went really wrong, log it and also give the error in twitch chat
                # Probably best to remove it from twitch chat later
                print(f"[Bot] Error: {e}")
                return f"erm what did u do: {e}"
        return NOT_IN_GAME

    async def rank(self):
        # Bad - should probably have a "main" boolean or get the current account.
        account = self.db.get_account_by_name_and_tag("backshotsdemon", "delux")
        accounts = self.db.get_all_accounts()
        if len(accounts) == 0:
            return "No accounts configured"
        for acc in accounts:
            try:
                result = await self.riot.get_runes_for(acc)
                if result is not None:
                    account = acc
                    break
            except Exception as e:
                # Something went really wrong, log it and also give the error in twitch chat
                # Probably best to remove it from twitch chat later
                print(f"[Bot] Error: {e}")
                return f"erm what did u do: {e}"
        return await self.riot.get_rank_for(account)
    
    async def get_current_champion(self):
        accounts = self.db.get_all_accounts()
        if len(accounts) == 0:
            return "No accounts configured"
        for acc in accounts:
            try:
                result = await self.riot.get_champion_for(acc)
                if result is not None:
                    return result
            except Exception as e:
                # Something went really wrong, log it and also give the error in twitch chat
                # Probably best to remove it from twitch chat later
                print(f"[Bot] Error: {e}")
                return f"erm what did u do: {e}"
        return None

    async def is_champion(self, champion_name: str):
        current_champion = await self.get_current_champion()
        return current_champion == champion_name
