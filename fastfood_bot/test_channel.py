import asyncio
from aiogram import Bot
from config import BOT_TOKEN, ADMIN_CHANNEL_ID

async def test_channel():
    print(f"Testing channel ID: {ADMIN_CHANNEL_ID} (Type: {type(ADMIN_CHANNEL_ID)})")
    bot = Bot(token=BOT_TOKEN)
    try:
        # Try sending as string
        print("Attempting to send as string...")
        await bot.send_message(ADMIN_CHANNEL_ID, "Test message (string ID)")
        print("Success (string ID)")
    except Exception as e:
        print(f"Failed (string ID): {e}")

    try:
        # Try sending as int
        int_id = int(ADMIN_CHANNEL_ID)
        print(f"Attempting to send as int: {int_id}...")
        await bot.send_message(int_id, "Test message (int ID)")
        print("Success (int ID)")
    except Exception as e:
        print(f"Failed (int ID): {e}")

    await bot.close()

if __name__ == "__main__":
    asyncio.run(test_channel())
