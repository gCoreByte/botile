import os

from champion_cache import ChampionCache
from rune_cache import RuneCache
from db import Account

class RiotClient:
    def __init__(self, session):
        self.session = session
        self.headers = {"X-Riot-Token": os.getenv("RIOT_API_KEY")}
        self.rune_cache = RuneCache()
        self.champion_cache = ChampionCache()

    async def get_puuid(self, name, tag):
        url = f"https://{os.getenv('RIOT_REGION')}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
        async with self.session.get(url, headers=self.headers) as resp:
            if resp.status == 200:
                return (await resp.json())["puuid"]
        return None

    async def get_current_match(self, puuid):
        url = f"https://{os.getenv('RIOT_PLATFORM')}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
        async with self.session.get(url, headers=self.headers) as resp:
            if resp.status == 200:
                return await resp.json()
        return None

    async def get_rune_names_from_match(self, match_data, puuid):
        player = next((p for p in match_data["participants"] if p["puuid"] == puuid), None)
        if not player:
            return []

        ids = player["perks"]["perkIds"]

        runes_json = await self.rune_cache.get(self.session)
        names = []

        for rune_id in ids:
            names.append(runes_json[rune_id]["name"])

        return names

    async def get_runes_for(self, account: Account):
        # PUUID does not change, we can cache it
        if not account.puuid:
            account.puuid = await self.get_puuid(account.name, account.tag)
            if not account.puuid:
                return "Could not find summoner."
            account.save()

        match = await self.get_current_match(account.puuid)
        if not match:
            return None

        runes = await self.get_rune_names_from_match(match, account.puuid)
        if not runes:
            print(f"[Riot] Could not find rune data for {account.name}.")
            return None

        return ', '.join(runes)

    async def get_summoner_data(self, puuid: str):
        url = f"https://{os.getenv('RIOT_PLATFORM')}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"

        async with self.session.get(url, headers=self.headers) as resp:
            if resp.status == 200:
                return await resp.json()
        return None

    async def get_rank_for(self, account: Account):
        if not account.puuid:
            account.puuid = await self.get_puuid(account.name, account.tag)
            if not account.puuid:
                return "Could not find summoner."
            account.save()

        data = await self.get_summoner_data(account.puuid)
        if data is None:
            return "Error"
        for league in data:
            if league['queueType'] == "RANKED_SOLO_5x5":
                # Handle master
                if league['tier'] == 'MASTER' or league['tier'] == "GRANDMASTER" or league['tier'] == 'CHALLENGER':
                    return f"{league['tier'].capitalize()} {league['leaguePoints']}LP"
                else:
                    return f"{league['tier'].capitalize()} {league['rank']} {league['leaguePoints']}LP"

    async def get_champion_for(self, account: Account):
        if not account.puuid:
            account.puuid = await self.get_puuid(account.name, account.tag)
            if not account.puuid:
                return "Could not find summoner."
            account.save()

        match = await self.get_current_match(account.puuid)
        if not match:
            return None
        
        player = next((p for p in match["participants"] if p["puuid"] == account.puuid), None)
        if not player:
            return None

        champion_id = player["championId"]
        champion_json = await self.champion_cache.get(self.session)
        champion_name = champion_json[champion_id]["name"]
        return champion_name
