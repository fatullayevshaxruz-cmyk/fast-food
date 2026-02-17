import asyncio
from aiogram import Bot
from config import BOT_TOKEN, ADMIN_CHANNEL_ID

async def debug_channel():
    bot = Bot(token=BOT_TOKEN)
    channel_id = int(ADMIN_CHANNEL_ID)
    print(f"Checking access to channel ID: {channel_id}")
    
    try:
        chat = await bot.get_chat(channel_id)
        print(f"SUCCESS! Found chat: {chat.title} (ID: {chat.id})")
        print(f"Type: {chat.type}")
        
        # Try sending a test message
        msg = await bot.send_message(channel_id, "Test message from debug script")
        print(f"Message sent successfully: ID {msg.message_id}")
    except Exception as e:
        print(f"ERROR: {e}")
        
    await bot.close()

if __name__ == "__main__":
    asyncio.run(debug_channel())
