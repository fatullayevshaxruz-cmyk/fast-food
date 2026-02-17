import asyncio
from aiogram import Bot, Dispatcher, types
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(content_types=types.ContentTypes.ANY)
async def handle_all(message: types.Message):
    if message.forward_from_chat:
        print(f"FORWARDED FROM CHAT: {message.forward_from_chat.title}")
        print(f"ID: {message.forward_from_chat.id}")
        await message.answer(f"Kanal ID: {message.forward_from_chat.id}")
    else:
        print(f"Message received: {message.text}")
        await message.answer("Iltimos, kanalizdan biron xabarni shu yerga 'Forward' (uzatish) qiling.")

async def main():
    print("Bot ishga tushdi. Kanal xabarini kutyapman...")
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
