import os
import random
import ssl
import aiohttp
import asyncio
import time
import re
from riot_client import RiotClient
from lolpros_api import LolprosApi
from deeplol_api import DeepLolApi
from db import Database, Account, Command

ADMIN_USERS = ["reptile9lol", "gcorebyte", "k1mbo9lol"]

NOT_IN_GAME = "Reptile is currently not in game"
SCRIMS = "reptile is currently in scrims, some commands are currently disabled"
COOLDOWN_TIME = 3

def is_admin(user: str):
    # This should probably check if the user is a mod too
    return user.lower().strip() in ADMIN_USERS


class TwitchBot:
    def __init__(self):
        self.reader = None
        self.writer = None
        self.riot = None
        self.lolpros = None
        self.deeplol = None
        self.db = Database()
        self.count = 1
        self.previous_message = ""
        self.last_message_sent_at = 0  # Initialize to 0 to allow first message
        self.quiet = False
        self.scrims = False

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
            self.deeplol = DeepLolApi(session)
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
        normalized_content = content.lower()
        match = re.search(r'PRIVMSG\s+(#[^\s:]+)\s+:', message)
        channel = match.group(1).strip()

        if self.quiet and (not normalized_content.startswith("!") or not is_admin(user)):
            return

        # FIXME
        if normalized_content.startswith("!runes"):
            if self.scrims:
                self.send(user, channel, SCRIMS)
                self.last_message_sent_at = current_time
                return
            result = await self.runes()
            self.send(user, channel, result)
            self.last_message_sent_at = current_time
        elif normalized_content.startswith("!pros"):
            if self.scrims:
                self.send(user, channel, SCRIMS)
                self.last_message_sent_at = current_time
                return
            result = await self.pros()
            if result is None:
                result = NOT_IN_GAME
            self.send(user, channel, result)
            self.last_message_sent_at = current_time
        elif normalized_content.startswith("!rank"):
            result = await self.rank()
            self.send(user, channel, result)
            self.last_message_sent_at = current_time
        elif normalized_content.startswith("!cutoff"):
            # result = await self.cutoff()
            result = "Currently disabled."
            self.send(user, channel, result)
            self.last_message_sent_at = current_time
        elif is_admin(user) and normalized_content.startswith("!"):
            if normalized_content.startswith("!addcmd"):
                # Format: !addcmd name keyword1,keyword2:message
                parts = normalized_content.removeprefix("!addcmd ").split(":", 1)
                if len(parts) == 2:
                    name_and_keywords, message = parts
                    # Split name and keywords (name is first word, rest are keywords)
                    name_keywords_parts = name_and_keywords.split(" ", 1)
                    if len(name_keywords_parts) == 2:
                        name, keywords_str = name_keywords_parts
                        keywords = [kw.strip() for kw in keywords_str.split(",")]
                        result = await self.add_keyword_command(channel, name, keywords, message)
                        self.send(user, channel, result)
                        self.last_message_sent_at = current_time
                    else:
                        self.send(user, channel, "Usage: !addcmd name keyword1,keyword2:message")
                        self.last_message_sent_at = current_time
                else:
                    self.send(user, channel, "Usage: !addcmd name keyword1,keyword2:message")
                    self.last_message_sent_at = current_time
            elif normalized_content.startswith("!delcmd"):
                # Format: !delcmd name
                name = normalized_content.removeprefix("!delcmd ").strip()
                if name:
                    result = await self.delete_keyword_command(channel, name)
                    self.send(user, channel, result)
                    self.last_message_sent_at = current_time
                else:
                    self.send(user, channel, "Usage: !delcmd name")
                    self.last_message_sent_at = current_time
            elif normalized_content.startswith("!cmds"):
                result = await self.list_keyword_commands(channel)
                self.send(user, channel, result)
                self.last_message_sent_at = current_time
            elif normalized_content.startswith("!add"):
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
            elif normalized_content.startswith("!scrims"):
                self.scrims = True
                self.send(user, channel, "gl in scrims bro")
                self.last_message_sent_at = current_time
            elif normalized_content.startswith("!live"):
                self.scrims = False
                self.send(user, channel, "20 game winstreak coming")
                self.last_message_sent_at = current_time
        else:
            # Check for keyword matches in command database when no commands have matched
            # First check for phrase matches (keywords with spaces) in the original content
            matched_command = self.db.find_command_with_phrase_match(channel, content)
            if matched_command:
                self.send(user, channel, matched_command.message)
                self.last_message_sent_at = current_time
            else:
                # If no phrase match, check for individual word matches
                words = content.split()
                if words:
                    # Find command with most matching keywords
                    matched_command = self.db.find_command_with_most_matching_keywords(channel, words)
                    if matched_command:
                        self.send(user, channel, matched_command.message)
                        self.last_message_sent_at = current_time
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
        
        highest_lp = 0
        highest_rank = None
        current_rank = None
        
        # Check all accounts once for both in-game status and rank
        for acc in accounts:
            try:
                # First check if in game
                in_game = await self.riot.get_runes_for(acc)
                rank_result = await self.riot.get_rank_for(acc)
                
                # Update highest LP if needed
                if rank_result[1] > highest_lp:
                    highest_lp = rank_result[1]
                    highest_rank = rank_result[0]
                
                # If in game, set as current rank
                if in_game is not None:
                    current_rank = rank_result[0]
            except Exception as e:
                print(f"[Bot] Error: {e}")
                return f"erm what did u do: {e}"
        
        if current_rank:
            return f"Highest: {highest_rank} | Current: {current_rank}"
        return highest_rank
    
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
    
    async def cutoff(self):
        data = await self.deeplol.get_cutoff_data()
        if data is None:
            return "Failed to get cutoff data"
        
        # Calculate time until 1:45 GMT+3 (22:45 UTC)
        now_utc = time.gmtime()
        target_hour = 22  # 1:45 GMT+3 = 22:45 UTC
        target_minute = 45
        
        # Create target time for today in UTC
        target_time = time.struct_time((
            now_utc.tm_year, now_utc.tm_mon, now_utc.tm_mday,
            target_hour, target_minute, 0,
            now_utc.tm_wday, now_utc.tm_yday, now_utc.tm_isdst
        ))
        
        # Convert to seconds since epoch
        now_seconds = time.mktime(now_utc)
        target_seconds = time.mktime(target_time)
        
        # If target time has passed today, add 24 hours
        if target_seconds < now_seconds:
            target_seconds += 24 * 3600
            
        # Calculate remaining seconds
        remaining_seconds = int(target_seconds - now_seconds)
        
        # Convert to HH:MM:SS
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        seconds = remaining_seconds % 60
        time_to_update = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return f"Challenger: {data['challenger']}LP | Grandmaster: {data['grandmaster']}LP | Next update in {time_to_update}"

    # Keyword command management methods
    async def add_keyword_command(self, channel: str, name: str, keywords: list[str], message: str):
        # Check if command already exists
        existing_command = self.db.get_command_by_name_and_channel(name, channel)
        if existing_command:
            return f"Command '{name}' already exists in this channel"
        
        command = Command(name=name, channel_name=channel, keywords=keywords, message=message)
        command.save()
        return f"Added keyword command '{name}': '{', '.join(keywords)}' -> '{message}'"

    async def delete_keyword_command(self, channel: str, name: str):
        command = self.db.get_command_by_name_and_channel(name, channel)
        if command:
            command.delete()
            return f"Deleted keyword command '{name}'"
        return f"Keyword command '{name}' not found in this channel"

    async def list_keyword_commands(self, channel: str):
        commands = self.db.get_commands_by_channel(channel)
        
        if len(commands) == 0:
            return "No keyword commands configured for this channel"
        
        command_names = [cmd.name for cmd in commands]
        return f"Commands: {', '.join(command_names)}"
