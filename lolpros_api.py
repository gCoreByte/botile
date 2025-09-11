import os
import asyncio
from champion_cache import ChampionCache
from db import Account

LOLPROS_API_URL = "https://api.lolpros.gg/lol/game"

class LolprosApi:
    def __init__(self, session, riotApi, twitchBot):
        self.session = session
        self.twitchBot = twitchBot
        self.champion_cache = ChampionCache()
        self.riotApi = riotApi
        self.last_request_cache = None
        self._request_semaphore = asyncio.Semaphore(1)  # Only allow 1 concurrent request

    async def _get_lolpros_data(self, account: Account, user: str, channel: str):
        async with self._request_semaphore:
            if self.last_request_cache is not None:
                current_game = await self.riotApi.get_current_match(account.puuid)
                if current_game is None:
                    print("[LolprosApi] No current game found. Resetting cache.")
                    self.last_request_cache = None
                    return None
            if self.last_request_cache is not None and current_game['gameId'] == self.last_request_cache['gameId']:
                print("[LolprosApi] Successful cache hit")
                return self.last_request_cache
            print("[LolprosApi] Cache miss. Fetching new data.")
            if user is not None and channel is not None:
                self.twitchBot.send(user, channel, "Fetching data from Lolpros, this might take a bit...")
            headers = { "Accept": "application/json", "Host": "api.lolpros.gg", "Lpgg-Server": "EUW" }
            params = { "query": account.name, "tagline": account.tag }
            async with self.session.get(LOLPROS_API_URL, params=params, headers=headers) as resp:
                if resp.status == 200:
                    response = await resp.json()
                    self.last_request_cache = response
                    return response
            return None

    def _dig(self, value, *keys):
        keys = list(keys)
        if len(keys) == 0 or isinstance(value, str):
            return value
        if value is None:
            return ""
        value = value.get(keys[0], "")
        return self._dig(value, *keys[1:])

    def _get_player_name(self, participant: {}, account: Account):
        if participant['riotId'].lower().strip() == account.full_name():
            return "Reptile"
        return f"{self._dig(participant['lolpros'], 'team', 'tag')} {self._dig(participant['lolpros'], 'name')}".strip()
    
    def _get_role(self, participant: {}, account: Account):
        if account.full_name() == participant['riotId'].lower().strip():
            return " | Bot"
        role = self._dig(participant['lolpros'], 'position')
        if "top" in role:
            return " | Top"
        elif "jungle" in role:
            return " | Jungle"
        elif "mid" in role:
            return " | Mid"
        elif "supp" in role:
            return " | Supp"
        elif "adc" in role:
            return " | Bot"
        return ""

    async def get_all_pro_names(self, account: Account, user: str, channel: str):
        data = await self._get_lolpros_data(account, user, channel)
        if data is None:
            return None

        champion_data = await self.champion_cache.get(self.session)
        red = []
        blue = []
        average_red_lp = 0
        average_blue_lp = 0
        for participant in data['participants']:
            champion_name = champion_data[participant['championId']]['name']
            player_name = self._get_player_name(participant, account)
            role = self._get_role(participant, account)
            formatted_string = f"{champion_name} ({player_name}{role})"
            if participant['teamId'] == 100:
                if player_name != "":
                    blue.append(formatted_string)
                average_blue_lp += participant['ranking']['leaguePoints']
            elif participant['teamId'] == 200:
                if player_name != "":
                    red.append(formatted_string)
                average_red_lp += participant['ranking']['leaguePoints']
        blue_formatted = f"🟦 (Average LP: {round(average_blue_lp / 5)}): {', '.join(blue)}"
        red_formatted= f"🟥 (Average LP: {round(average_red_lp / 5)}): {', '.join(red)}"
        final = ""
        final += blue_formatted
        final += " ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯ "
        final += red_formatted
        return final
