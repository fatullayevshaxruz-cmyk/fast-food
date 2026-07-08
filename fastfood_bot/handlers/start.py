from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from database.crud import create_user, get_user_language, set_user_language
from keyboards.main_menu import get_user_main_menu, get_admin_main_menu, get_language_keyboard, MENU_WEBAPP_URL
from utils.states import LanguageStates
from utils.i18n import get_text
from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END, DELIVERY_FEE, MIN_ORDER_AMOUNT


# Til tugmalariga mos kalit
LANG_BUTTON_MAP = {
    "🇺🇿 O'zbek": "uz",
    "🇷🇺 Русский": "ru",
    "🇬🇧 English": "en",
}


def _is_admin(user_id):
    return str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]


async def cmd_start(message: types.Message, state: FSMContext):
    """Botni boshlash — avval til tanlash."""
    user = message.from_user
    # Foydalanuvchini DBga qo'shish
    await create_user(user.id, user.username, user.full_name)

    # Har doim til tanlash so'raladi (qayta /start bosish = til o'zgartirish)
    await LanguageStates.choosing_language.set()
    await message.answer(
        "🌐 Tilni tanlang / Выберите язык / Choose language:",
        reply_markup=get_language_keyboard()
    )


async def process_language_choice(message: types.Message, state: FSMContext):
    """Til tanlandi — DBga saqlash va asosiy menyuni ko'rsatish."""
    text = message.text.strip()
    lang = LANG_BUTTON_MAP.get(text)

    if not lang:
        # Noto'g'ri tugma — qayta so'rash
        await message.answer(
            "❓ Iltimos, quyidagi tugmalardan birini bosing:\n"
            "Please choose one of the buttons below:",
            reply_markup=get_language_keyboard()
        )
        return

    user = message.from_user

    # Tilni DBga saqlash
    await set_user_language(user.id, lang)
    await state.finish()

    # Tanlangan til haqida tasdiqlash va ReplyKeyboard ni yashirish
    from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    await message.answer(get_text("language_selected", lang), reply_markup=ReplyKeyboardRemove())

    # WebApp URL
    webapp_url = f"{MENU_WEBAPP_URL}?lang={lang}"

    # Asosiy menyu uchun inline tugmalar
    inline_kb = InlineKeyboardMarkup(row_width=1)
    inline_kb.add(
        InlineKeyboardButton(
            text="🌐 Menu ilova",
            web_app=WebAppInfo(url=webapp_url)
        ),
        InlineKeyboardButton(
            text="📱 Menu",
            callback_data="show_regular_menu"
        )
    )

    await message.answer(
        get_text("welcome", lang,
                 name=user.full_name,
                 start=WORKING_HOURS_START,
                 end=WORKING_HOURS_END,
                 fee=DELIVERY_FEE,
                 min_order=MIN_ORDER_AMOUNT),
        reply_markup=inline_kb,
        parse_mode="HTML"
    )


async def cmd_webapp(message: types.Message, state: FSMContext):
    """
    /webapp — WebApp interaktiv menyuni to'g'ridan-to'g'ri ochish.
    Keyboard yangilanmaganda ham ishlaydi.
    """
    try:
        lang = await get_user_language(message.from_user.id)
    except Exception:
        lang = "uz"

    webapp_url = f"{MENU_WEBAPP_URL}?lang={lang}"

    # Inline klaviatura orqali WebApp tugmasi yuborish
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            text="Menu",
            web_app=WebAppInfo(url=webapp_url)
        )
    )
    labels = {
        "uz": "👇 Quyidagi tugmani bosib menyuni oching:",
        "ru": "👇 Нажмите кнопку ниже для открытия меню:",
        "en": "👇 Press the button below to open the menu:",
    }
    await message.answer(labels.get(lang, labels["uz"]), reply_markup=markup)


async def cmd_refresh_menu(message: types.Message, state: FSMContext):
    """
    /menu_refresh — Klaviaturani yangilash (WebApp tugmasi ko'rinmasa).
    """
    try:
        lang = await get_user_language(message.from_user.id)
    except Exception:
        lang = "uz"
    await state.finish()
    keyboard = get_admin_main_menu(lang) if _is_admin(message.from_user.id) else get_user_main_menu(lang)
    labels = {
        "uz": "✅ Menyu yangilandi! Endi <b>🌐 Tezkor buyurtma</b> tugmasini ko'rishingiz mumkin.",
        "ru": "✅ Меню обновлено! Теперь вы увидите кнопку <b>🌐 Быстрый заказ</b>.",
        "en": "✅ Menu refreshed! You can now see the <b>🌐 Quick Order</b> button.",
    }
    await message.answer(labels.get(lang, labels["uz"]), reply_markup=keyboard, parse_mode="HTML")


async def cmd_help(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    await message.answer(
        get_text("help_text", lang,
                 start=WORKING_HOURS_START,
                 end=WORKING_HOURS_END),
        parse_mode="HTML"
    )


async def cmd_cancel(message: types.Message, state: FSMContext):
    """Istalgan holatda /cancel buyrug'i — jarayonni bekor qiladi."""
    current = await state.get_state()
    lang = await get_user_language(message.from_user.id)
    if current:
        await state.finish()
        keyboard = get_admin_main_menu(lang) if _is_admin(message.from_user.id) else get_user_main_menu(lang)
        await message.answer(
            get_text("cancel_ok", lang),
            reply_markup=keyboard
        )
    else:
        await message.answer(get_text("no_active_action", lang))


async def process_show_regular_menu_callback(call: types.CallbackQuery):
    """'Oddiy menu' tugmasi bosilganda an'anaviy klaviaturani chiqaradi."""
    await call.answer()
    try:
        lang = await get_user_language(call.from_user.id)
    except Exception:
        lang = "uz"

    keyboard = get_admin_main_menu(lang) if _is_admin(call.from_user.id) else get_user_main_menu(lang)
    labels = {
        "uz": "📱 Oddiy menyu ochildi. Quyidagi klaviaturadan foydalaning:",
        "ru": "📱 Обычное меню открыто. Используйте клавиатуру ниже:",
        "en": "📱 Regular menu opened. Use the keyboard below:",
    }
    await call.message.answer(labels.get(lang, labels["uz"]), reply_markup=keyboard)


def register_start_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=['start'], state="*")
    dp.register_message_handler(process_language_choice,
                                state=LanguageStates.choosing_language)
    dp.register_callback_query_handler(process_show_regular_menu_callback, text="show_regular_menu", state="*")
    dp.register_message_handler(cmd_help, commands=['help'])
    dp.register_message_handler(cmd_cancel, commands=['cancel'], state="*")
    dp.register_message_handler(cmd_webapp, commands=['webapp'], state="*")           # 🌐 WebApp
    dp.register_message_handler(cmd_refresh_menu, commands=['menu_refresh'], state="*")  # 🔄 Yangilash

