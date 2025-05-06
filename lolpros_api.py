import os
from champion_cache import ChampionCache
from db import Account

LOLPROS_API_URL = "https://api.lolpros.gg/lol/game"

class LolprosApi:
    def __init__(self, session):
        self.session = session
        self.champion_cache = ChampionCache()

    async def _get_lolpros_data(self, account: Account):
        headers = { "Accept": "application/json", "Host": "api.lolpros.gg", "Lpgg-Server": "EUW" }
        params = { "query": account.name, "tagline": account.tag }
        async with self.session.get(LOLPROS_API_URL, params=params, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
        return None

    def _dig(self, value, *keys):
        if len(keys) == 0 or isinstance(value, str):
            return value
        if value is None:
            return ""
        value = value.get(keys[0], "")
        return self._dig(value, keys[1:])

    def _get_player_name(self, participant: {}, account: Account):
        if participant['riotId'].lower().strip() == account.full_name():
            return "CGN Reptile"
        return f"{self._dig(participant['lolpros'], 'team', 'tag')} {self._dig(participant['lolpros'], 'name')}".strip()

    async def get_all_pro_names(self, account: Account):
        data = await self._get_lolpros_data(account)
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
            formatted_string = f"{champion_name} ({player_name})"
            if participant['teamId'] == 100:
                if player_name is not None:
                    blue.append(formatted_string)
                average_blue_lp += participant['ranking']['leaguePoints']
            elif participant['teamId'] == 200:
                if player_name is not None:
                    red.append(formatted_string)
                average_red_lp += participant['ranking']['leaguePoints']
        blue_formatted = f"🟦 (Average LP: {round(average_blue_lp / 5)}): {', '.join(blue)}"
        red_formatted= f"🟥 (Average LP: {round(average_red_lp / 5)}): {', '.join(red)}"
        final = ""
        final += blue_formatted
        final += " ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯ "
        final += red_formatted
        return final
