"""
handlers/webapp_menu.py
========================
Telegram WebApp interaktiv menyusidan kelgan savat ma'lumotlarini
qayta ishlash.

Oqim:
  1. Foydalanuvchi webapp/menu.html da mahsulot tanlab "Buyurtma berish" bosadi
  2. Telegram.WebApp.sendData(JSON) → bot WEB_APP_DATA xabari oladi
  3. Bu handler JSON ni parse qilib, savatga qo'shadi va checkout boshlaydi

Mavjud handler (process_webapp_location) bilan to'qnashuv yo'q:
  - process_webapp_location → state=waiting_for_location da ishlaydi
  - process_webapp_cart     → type="webapp_cart" JSON filtri bilan ishlaydi
"""

import json
import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import ContentTypes, ReplyKeyboardMarkup, KeyboardButton

from database.crud import clear_cart, add_to_cart, get_user_language
from utils.i18n import get_text
from utils.states import OrderStates
from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END

log = logging.getLogger(__name__)


# ── Filter: faqat "webapp_cart" tipidagi WebApp dataga mos keladi ─────

def _is_webapp_cart(message: types.Message) -> bool:
    """Faqat webapp menyu dan yuborilgan savat ma'lumotiga mos keladi."""
    try:
        if not message.web_app_data:
            return False
        data = json.loads(message.web_app_data.data)
        return data.get("type") == "webapp_cart"
    except Exception:
        return False


def _is_working_hours() -> bool:
    from datetime import datetime
    now = datetime.utcnow()
    uz_hour = (now.hour + 5) % 24
    return WORKING_HOURS_START <= uz_hour < WORKING_HOURS_END


def _get_menu_for_user(user_id, lang="uz"):
    from keyboards.main_menu import get_admin_main_menu, get_user_main_menu
    is_admin = str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return get_admin_main_menu(lang) if is_admin else get_user_main_menu(lang)


# ── Asosiy handler ────────────────────────────────────────────────────

async def process_webapp_cart(message: types.Message, state: FSMContext):
    """
    WebApp dan kelgan savat ma'lumotini qayta ishlash:
      1. Savatni tozalash
      2. Yangi mahsulotlarni qo'shish
      3. Checkout boshlash (yetkazish turi so'rash)
    """
    try:
        lang = await get_user_language(message.from_user.id)

        # Ish vaqtini tekshirish
        if not _is_working_hours():
            from config import WORKING_HOURS_START as WS, WORKING_HOURS_END as WE
            await message.answer(
                get_text("not_working_hours", lang, start=WS, end=WE),
                parse_mode="HTML"
            )
            return

        raw = message.web_app_data.data
        data = json.loads(raw)
        items = data.get("items", [])

        if not items:
            await message.answer(get_text("webapp_cart_empty", lang))
            return

        user_id = message.from_user.id

        # 1. Mavjud savatni tozalash
        await clear_cart(user_id)

        # 2. Yangi mahsulotlarni qo'shish
        added_count = 0
        for item in items:
            pid = item.get("product_id")
            qty = max(1, int(item.get("quantity", 1)))
            if pid and qty > 0:
                await add_to_cart(user_id, int(pid), qty)
                added_count += qty

        if added_count == 0:
            await message.answer(get_text("webapp_cart_empty", lang))
            return

        # 3. Mavjud FSM holatini yakunlash (agar bo'lsa)
        await state.finish()

        # 4. Checkout boshlash
        await OrderStates.waiting_for_delivery_type.set()

        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            KeyboardButton(get_text("btn_eat_in", lang)),
            KeyboardButton(get_text("btn_delivery", lang)),
        )
        markup.add(KeyboardButton(get_text("btn_cancel", lang)))

        await message.answer(
            get_text("webapp_cart_received", lang),
            reply_markup=markup,
            parse_mode="HTML",
        )

        log.info(
            f"WebApp savat qabul qilindi: user={user_id}, "
            f"{len(items)} mahsulot turi, jami {added_count} dona"
        )

    except json.JSONDecodeError:
        log.error("WebApp savat: JSON parse xatosi")
        try:
            lang = await get_user_language(message.from_user.id)
            await message.answer(get_text("webapp_cart_empty", lang))
        except Exception:
            pass
    except Exception as e:
        log.error(f"WebApp savat xatosi: {e}", exc_info=True)
        try:
            lang = await get_user_language(message.from_user.id)
            await message.answer(get_text("webapp_cart_empty", lang))
        except Exception:
            pass


# ── Handlerlarni ro'yxatdan o'tkazish ────────────────────────────────

def register_webapp_menu_handlers(dp: Dispatcher):
    """
    WebApp cart handlerini ro'yxatdan o'tkazadi.

    MUHIM: Bu handler register_order_handlers() DAN KEYIN ro'yxatdan o'tkaziladi.
    Natijada:
      - state=waiting_for_location + WEB_APP_DATA → process_webapp_location (avvalgi)
      - type="webapp_cart" + WEB_APP_DATA         → process_webapp_cart (bu)
    """
    dp.register_message_handler(
        process_webapp_cart,
        _is_webapp_cart,
        content_types=ContentTypes.WEB_APP_DATA,
        state="*",
    )
