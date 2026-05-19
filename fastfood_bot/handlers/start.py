from aiogram import types, Dispatcher
from database.crud import create_user
from keyboards.main_menu import get_user_main_menu, get_admin_main_menu
from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END


async def cmd_start(message: types.Message):
    user = message.from_user
    await create_user(user.id, user.username, user.full_name)

    # Admin bo'lsa menyu boshqaruvi tugmasi ham ko'rinadi
    is_admin = str(user.id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    keyboard = get_admin_main_menu() if is_admin else get_user_main_menu()

    await message.answer(
        f"🍔 <b>Fast Food</b> ga xush kelibsiz, <b>{user.full_name}</b>!\n\n"
        f"Tez va mazali taomlar — bir tugma bilan! 🚀\n\n"
        f"📱 <b>Buyurtma berish:</b> \"🍽 Menu\" tugmasini bosing\n"
        f"🔍 <b>Mahsulot izlash:</b> \"🔍 Izlash\" tugmasini bosing\n"
        f"📦 <b>Buyurtmalaringiz:</b> \"📦 Buyurtmalarim\"\n\n"
        f"🕐 <b>Ish vaqti:</b> {WORKING_HOURS_START:02d}:00 — {WORKING_HOURS_END:02d}:00\n"
        f"🛵 <b>Yetkazib berish:</b> butun shahar bo'ylab\n\n"
        f"Yoqimli ishtaha tilaymiz! 😋",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


def register_start_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=['start'])
