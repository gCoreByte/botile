import asyncio
import os
from dotenv import load_dotenv

from db import Database
from twitch_bot import TwitchBot

async def main():
    load_dotenv()
    # SQLite3 tables
    Database().create_tables()
    bot = TwitchBot()
    await bot.connect()
    await bot.listen()

if __name__ == "__main__":
    asyncio.run(main())
