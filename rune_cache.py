import time

CACHE_DURATION = 60 * 60 * 24 * 7 # 1 week, this will basically never change for this use case

class RuneCache:
    def __init__(self):
        self.raw_data = None
        self.data = None
        self.last_fetched = 0

    async def get(self, session):
        now = time.time()
        if self.data and (now - self.last_fetched < CACHE_DURATION):
            return self.data

        print("[RuneCache] Refreshing rune data...")
        url = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/perks.json"
        async with session.get(url) as resp:
            if resp.status == 200:
                self.raw_data = await resp.json()
                self.last_fetched = now
                self.data = {}
                for obj in self.raw_data:
                    self.data[obj["id"]] = obj
            else:
                print(f"[RuneCache] Failed to fetch: {resp.status}")
        return self.data or [] 