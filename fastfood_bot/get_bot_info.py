import asyncio
from aiogram import Bot
from config import BOT_TOKEN

async def get_bot_info():
    bot = Bot(token=BOT_TOKEN)
    try:
        user = await bot.get_me()
        print(f"Bot Username: @{user.username}")
        print(f"Bot Link: https://t.me/{user.username}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(get_bot_info())
