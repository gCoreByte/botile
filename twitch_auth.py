import asyncio
import os
import aiojobs

from aiohttp import ClientSession
from aiofiles import open as aio_open

from server import Server

TWITCH_OAUTH_URL = "https://id.twitch.tv/oauth2/token"


def _headers(token: str):
    return { "Authorization": f"OAuth {token}" }


class TwitchAuth:
    def __init__(self, server: Server, session: ClientSession):
        self.session: ClientSession = session
        self.token_path = "token.data"
        self.app_access_token = None
        self.user_access_token = None
        self.user_refresh_token = None

        self.scheduler = None
        server.on_startup.append(self._start_background_validator)
        server.on_cleanup.append(self._stop_background_validator)

    async def get_app_access_token(self):
        if self.app_access_token:
            return self.app_access_token
        return await self._authenticate_app()

    async def get_user_access_token(self):
        if not self.user_refresh_token:
            await self._load_token()
        if self.user_access_token:
            return self.user_access_token
        return await self._refresh_user_token()

    async def _start_background_validator(self, _app: Server):
        self.scheduler = await aiojobs.create_scheduler()
        await self.scheduler.spawn(self._token_validation_loop())

    async def _stop_background_validator(self, _app: Server):
        if self.scheduler:
            await self.scheduler.close()

    async def _token_validation_loop(self):
        while True:
            await self._validate_tokens()
            await asyncio.sleep(3600)

    async def _validate_tokens(self):
        if not self._validate_token(self.user_access_token):
            return await self._refresh_user_token()
        if not self._validate_token(self.app_access_token):
            return await self._authenticate_app()

    async def _validate_token(self, token: str):
        async with self.session.get("https://id.twitch.tv/oauth2/validate", headers=_headers(token)) as resp:
            return resp.status == 200

    async def _authenticate_app(self):
        payload = {
            "client_id": os.getenv("TWITCH_CLIENT_ID"),
            "client_secret": os.getenv("TWITCH_CLIENT_SECRET"),
            "grant_type": "client_credentials"
        }
        async with self.session.post(TWITCH_OAUTH_URL, data=payload) as resp:
            json_response = await resp.json()
            self.app_access_token = json_response["access_token"]
        return self.app_access_token

    async def _refresh_user_token(self):
        payload = {
            "client_id": os.getenv("TWITCH_CLIENT_ID"),
            "client_secret": os.getenv("TWITCH_CLIENT_SECRET"),
            "grant_type": "refresh_token",
            "refresh_token": self.user_refresh_token
        }
        async with self.session.post(TWITCH_OAUTH_URL, data=payload) as resp:
            json_response = await resp.json()
            self.user_access_token = json_response["access_token"]
            self.user_refresh_token = json_response["refresh_token"]
            await self._save_token()
        return self.user_access_token

    async def _load_token(self):
        try:
            async with aio_open(self.token_path, mode="r") as f:
                self.user_refresh_token = (await f.read()).strip()
        except:
            raise FileNotFoundError(f"[TwitchAuth] Refresh token file not found at {self.token_path}. Please authenticate manually.")

    async def _save_token(self):
        async with aio_open(self.token_path, mode="w") as f:
            await f.write(self.user_refresh_token)