from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from database.crud import create_user
from keyboards.main_menu import get_user_main_menu, get_admin_main_menu
from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END, DELIVERY_FEE, MIN_ORDER_AMOUNT


def _is_admin(user_id):
    return str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]


async def cmd_start(message: types.Message):
    user = message.from_user
    await create_user(user.id, user.username, user.full_name)
    keyboard = get_admin_main_menu() if _is_admin(user.id) else get_user_main_menu()

    await message.answer(
        f"🍔 <b>Fast Food</b> ga xush kelibsiz, <b>{user.full_name}</b>!\n\n"
        f"Tez va mazali taomlar — bir tugma bilan! 🚀\n\n"
        f"📱 <b>Buyurtma berish:</b> \"🍽 Menu\" tugmasini bosing\n"
        f"🔍 <b>Mahsulot izlash:</b> \"🔍 Izlash\" tugmasini bosing\n"
        f"📦 <b>Buyurtmalaringiz:</b> \"📦 Buyurtmalarim\"\n\n"
        f"🕐 <b>Ish vaqti:</b> {WORKING_HOURS_START:02d}:00 — {WORKING_HOURS_END:02d}:00\n"
        f"🛵 <b>Yetkazib berish:</b> {DELIVERY_FEE:,} so'm\n"
        f"📋 <b>Minimal buyurtma:</b> {MIN_ORDER_AMOUNT:,} so'm (yetkazib berish uchun)\n\n"
        f"Yoqimli ishtaha tilaymiz! 😋",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Yordam — Bot qo'llanmasi</b>\n\n"
        "🍽 <b>Menu</b> — Barcha taomlarni ko'rish\n"
        "🛒 <b>Savat</b> — Savatni ko'rish va buyurtma berish\n"
        "🔍 <b>Izlash</b> — Mahsulot nomi bo'yicha qidiruv\n"
        "❤️ <b>Sevimlilar</b> — Saqlangan mahsulotlar\n"
        "📦 <b>Buyurtmalarim</b> — Barcha buyurtmalar tarixi\n"
        "👤 <b>Profil</b> — Shaxsiy ma'lumotlarni tahrirlash\n"
        "☎️ <b>Biz bilan aloqa</b> — Muammo bo'lsa bog'laning\n\n"
        "⚡ <b>Foydali buyruqlar:</b>\n"
        "/start — Botni qayta ishga tushirish\n"
        "/cancel — Joriy amalni bekor qilish\n"
        "/help — Shu yordam oynasi\n\n"
        f"🕐 <b>Ish vaqti:</b> {WORKING_HOURS_START:02d}:00 — {WORKING_HOURS_END:02d}:00\n"
        f"📞 <b>Aloqa:</b> +998943265755",
        parse_mode="HTML"
    )


async def cmd_cancel(message: types.Message, state: FSMContext):
    """Istalgan holatda /cancel buyrug'i — jarayonni bekor qiladi."""
    current = await state.get_state()
    if current:
        await state.finish()
        keyboard = get_admin_main_menu() if _is_admin(message.from_user.id) else get_user_main_menu()
        await message.answer(
            "❌ Joriy amal bekor qilindi.",
            reply_markup=keyboard
        )
    else:
        await message.answer("Hozir bekor qilish uchun faol amal yo'q.")


def register_start_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=['start'])
    dp.register_message_handler(cmd_help, commands=['help'])
    dp.register_message_handler(cmd_cancel, commands=['cancel'], state="*")
