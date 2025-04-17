import os
from champion_cache import ChampionCache

class LolprosApi:
    def __init__(self, session):
        self.session = session
        # Can we generate this somehow?
        self.lolpros_url = os.getenv('LOLPROS_URL')
        self.champion_cache = ChampionCache()

    async def _get_lolpros_data(self):
        async with self.session.get(self.lolpros_url) as resp:
            if resp.status == 200:
                return await resp.json()
        return None

    def _dig(self, value, *keys):
        if len(keys) == 0 or isinstance(value, str):
            return value
        if value is None:
            return "Unknown"
        value = value.get(keys[0], "Unknown")
        return self._dig(value, keys[1:])

    def _get_player_name(self, participant: {}):
        return self._dig(participant['lolpros'], "name")

    async def get_all_pro_names(self):
        data = await self._get_lolpros_data()
        if data is None:
            return 'Something went wrong with the API call'

        champion_data = await self.champion_cache.get(self.session)
        red = []
        blue = []
        for participant in data['participants']:
            champion_name = champion_data[participant['championId']]['name']
            formatted_string = f"{champion_name} ({self._get_player_name(participant)})"
            if participant['teamId'] == 100:
                blue.append(formatted_string)
            elif participant['teamId'] == 200:
                red.append(formatted_string)
        return f"Blue: {', '.join(blue)} | Red: {', '.join(red)}"

