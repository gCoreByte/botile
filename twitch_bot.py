import os
import ssl
import aiohttp
import asyncio
from riot_client import RiotClient
from db import Database, Account

ADMIN_USERS = ["reptile9lol", "gcorebyte", "k1mbo9lol"]


def is_admin(user: str):
    # This should probably check if the user is a mod too
    return user.lower().strip() in ADMIN_USERS


class TwitchBot:
    def __init__(self):
        self.reader = None
        self.writer = None
        self.riot = None
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
        print("[Bot] Connected to Twitch")

    def _send(self, message, log=True):
        if log:
            # Debugging purposes
            print(f"[SEND] {message}")
        self.writer.write(f"{message}\r\n".encode())

    def send(self, user, twitch_channel, message):
        self._send(f"PRIVMSG {twitch_channel} :@{user}, {message}")

    def send_without_mention(self, twitch_channel, message):
        self._send(f"PRIVMSG {twitch_channel} :{message}")

    async def listen(self):
        async with aiohttp.ClientSession() as session:
            self.riot = RiotClient(session)
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
        content = message.split(":", 2)[2]
        # Processing
        content = content.removesuffix("  󠀀") # 7tv send twice hack
        content = content.removesuffix(" 󠀀")
        content = content.strip()

        # FIXME
        if content.startswith("!runes"):
            result = await self.runes()
            self.send(user, os.getenv('TWITCH_CHANNEL'), result)
        elif is_admin(user) and content.startswith("!"):
            if content.startswith("!add"):
                name, tag = content.removeprefix("!add ").split("#")
                result = await self.add_account(name, tag)
                self.send(user, os.getenv('TWITCH_CHANNEL'), result)
            elif content.startswith("!delete"):
                name, tag = content.removeprefix("!delete ").split("#")
                result = await self.delete_account(name, tag)
                self.send(user, os.getenv('TWITCH_CHANNEL'), result)
            elif content.startswith("!accounts"):
                result = await self.accounts()
                self.send(user, os.getenv('TWITCH_CHANNEL'), result)
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
        return "Reptile isn't in game right now"

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