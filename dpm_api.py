import os
from champion_cache import ChampionCache
from db import Account

DPM_API_URL = "https://dpm.lol/v1/players"

class DpmApi:
    def __init__(self, session):
        self.session = session
        self.last_request_cache = None

    async def _get_dpm_data(self, account: Account, riotApi):
        if self.last_request_cache is not None:
            current_game = await riotApi.get_current_match(account.puuid)
            if current_game is None:
                self.last_request_cache = None
                return None
        if current_game['gameId'] == self.last_request_cache['gameId']:
            return self.last_request_cache
        headers = { "Accept": "application/json" }
        url = f"{DPM_API_URL}/{account.puuid}/live"
        async with self.session.get(url, headers=headers) as resp:
            if resp.status == 200:
                json_response = await resp.json()
                self.last_request_cache = json_response
                return json_response
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
        if participant['puuid'] == account.puuid:
            return "Reptile"
        return f"{participant['team']} {participant['displayName']}".strip()
    
    def _get_role(self, participant: {}, account: Account):
        if account.puuid == participant['puuid']:
            return " | Bot"
        stats = participant['roleStats']
        role = stats[0]
        if "TOP" in role['role']:
            return " | Top"
        elif "JUNGLE" in role['role']:
            return " | Jungle"
        elif "MID" in role['role']:
            return " | Mid"
        elif "UTILITY" in role['role']:
            return " | Supp"
        elif "BOTTOM" in role['role']:
            return " | Bot"
        return ""

    async def get_all_pro_names(self, account: Account, riotApi):
        data = await self._get_dpm_data(account, riotApi)
        if data is None:
            return None

        champion_data = await self.champion_cache.get(self.session)
        red = []
        blue = []
        average_red_lp = 0
        average_blue_lp = 0
        for participant in data['participants']:
            champion_name = participant['championName']
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
