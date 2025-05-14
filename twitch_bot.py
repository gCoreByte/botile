import os
import random
import ssl
import aiohttp
import asyncio
import time
from riot_client import RiotClient
from lolpros_api import LolprosApi
from db import Database, Account

ADMIN_USERS = ["reptile9lol", "gcorebyte", "k1mbo9lol"]

NOT_IN_GAME = "Reptile is currently not in game"
COOLDOWN_TIME = 10

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
        self.last_message_sent_at = 0  # Initialize to 0 to allow first message
        self.quiet = False

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
        self._send(f"JOIN #gcorebyte")
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
        # Check rate limiting
        current_time = time.time()
        if current_time - self.last_message_sent_at < COOLDOWN_TIME:
            return  # Skip processing if less than 10 seconds have passed

        user = message.split("!", 1)[0][1:]
        content: str = message.split(":", 2)[2]
        if user.lower() == "nightbot" or user.lower() == "botile9lol":
            return
        # Processing
        content = content.removesuffix("  󠀀") # 7tv send twice hack
        content = content.removesuffix(" 󠀀")
        content = content.strip()
        channel = message.split(":", 2)[1].strip()
        normalized_content = content.lower()

        if self.quiet and (not normalized_content.startswith("!") or not is_admin(user)):
            return

        # FIXME
        if normalized_content.startswith("!runes"):
            result = await self.runes()
            self.send(user, channel, result)
            self.last_message_sent_at = current_time
        elif normalized_content.startswith("!pros"):
            result = await self.pros()
            if result is None:
                result = NOT_IN_GAME
            self.send(user, channel, result)
            self.last_message_sent_at = current_time
        elif normalized_content.startswith("!rank"):
            result = await self.rank()
            self.send(user, channel, result)
            self.last_message_sent_at = current_time
        elif not normalized_content.startswith("!") and "skin" in normalized_content and ("what" in normalized_content or "which" in normalized_content):
            current_champion = await self.get_current_champion()
            if current_champion == "Zeri":
                self.send(user, channel, "high noon zeri, custom skin from https://runeforge.dev/mods/f03862cc-4324-4f18-bd64-df0c376785cb")
                self.last_message_sent_at = current_time
            elif current_champion == "Vayne":
                self.send(user, channel, "kda all out vayne, custom skin from https://www.runeforge.io/post/k-da-all-out-vayne")
                self.last_message_sent_at = current_time
            elif current_champion == "Xayah":
                self.send(user, channel, "winterblessed xayah, custom skin from https://www.runeforge.io/post/winterblessed-xayah")
                self.last_message_sent_at = current_time
        elif not normalized_content.startswith("!") and "zeri" in normalized_content and "skin" in normalized_content:
            self.send(user, channel, "high noon zeri, custom skin from https://runeforge.dev/mods/f03862cc-4324-4f18-bd64-df0c376785cb")
            self.last_message_sent_at = current_time
        elif not normalized_content.startswith("!") and "vayne" in normalized_content and "skin" in normalized_content:
            self.send(user, channel, "kda all out vayne, custom skin from https://www.runeforge.io/post/k-da-all-out-vayne")
            self.last_message_sent_at = current_time
        elif not normalized_content.startswith("!") and "xayah" in normalized_content and "skin" in normalized_content:
            self.send(user, channel, "winterblessed xayah, custom skin from https://www.runeforge.io/post/winterblessed-xayah")
            self.last_message_sent_at = current_time
        elif not normalized_content.startswith("!") and "delay" in normalized_content:
            self.send_without_mention(channel, "!delay")
            self.last_message_sent_at = current_time
        elif not normalized_content.startswith("!") and ("bald" in normalized_content or "haircut" in normalized_content):
            self.send_without_mention(channel, "true")
            self.last_message_sent_at = current_time
        elif "hob" in normalized_content or "hail of blade" in normalized_content:
            text = "LT is really slow to stack and doesn't give too much value when stacked. Because Zeri turns AS past 1.5 into AD, with HOB you get a big burst to AD immediately in fights."
            if "zeri" in normalized_content:
                self.send(user, channel, text)
                self.last_message_sent_at = current_time
                return
            result = await self.is_champion("Zeri")
            if result:
                self.send(user, channel, text)
                self.last_message_sent_at = current_time
        elif is_admin(user) and normalized_content.startswith("!"):
            if normalized_content.startswith("!add"):
                name, tag = normalized_content.removeprefix("!add ").split("#")
                result = await self.add_account(name, tag)
                self.send(user, channel, result)
                self.last_message_sent_at = current_time
            elif normalized_content.startswith("!delete"):
                name, tag = normalized_content.removeprefix("!delete ").split("#")
                result = await self.delete_account(name, tag)
                self.send(user, channel, result)
                self.last_message_sent_at = current_time
            elif normalized_content.startswith("!accounts"):
                result = await self.accounts()
                self.send(user, channel, result)
                self.last_message_sent_at = current_time
            elif normalized_content.startswith("!restart"):
                self.send(user, channel, "Restarting...")
                self.last_message_sent_at = current_time
                exit(0)
            elif normalized_content.startswith("!s "):
                self.send_without_mention(channel, content.removeprefix("!s "))
                self.last_message_sent_at = current_time
            elif normalized_content.startswith("!stfu"):
                self.quiet = True
                self.send(user, channel, "stfuing bye")
            elif normalized_content.startswith("!speak"):
                self.quiet = False
                self.send(user, channel, "hi")
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
            self.send_without_mention(channel, self.previous_message)

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
        accounts = self.db.get_all_accounts()
        if len(accounts) == 0:
            return "No accounts configured"
        # Get rank for currently in game account
        for acc in accounts:
            try:
                result = await self.riot.get_runes_for(acc)
                if result is not None:
                    res = await self.riot.get_rank_for(acc)
                    return res[0]
            except Exception as e:
                # Something went really wrong, log it and also give the error in twitch chat
                # Probably best to remove it from twitch chat later
                print(f"[Bot] Error: {e}")
                return f"erm what did u do: {e}"
        # Fallback to highest lp account
        highest_lp = 0
        res = None
        for acc in accounts:
            try:
                result = await self.riot.get_rank_for(acc)
                if result[1] > highest_lp:
                    highest_lp = result[1]
                    res = result[0]
            except Exception as e:
                # Something went really wrong, log it and also give the error in twitch chat
                # Probably best to remove it from twitch chat later
                print(f"[Bot] Error: {e}")
                return f"erm what did u do: {e}"
        return res
    
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
