DEEPLOL_API_URL = "https://b2c-api-cdn.deeplol.gg/summoner/summoner_rank?platform_id=EUW1&lane=All&page=1"

class DeepLolApi:
    def __init__(self, session):
        self.session = session

    async def _get_deep_lol_data(self):
        headers = { "Accept": "application/json" }
        async with self.session.get(DEEPLOL_API_URL, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
        return None

    async def get_cutoff_data(self):
        data = await self._get_deep_lol_data()
        if data is None:
            return None
        
        return {
            "challenger": data['challenger_cut_off'],
            "grandmaster": data['grandmaster_cut_off']
        }
