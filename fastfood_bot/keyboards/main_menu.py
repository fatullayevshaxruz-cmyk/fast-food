import os
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from utils.i18n import get_text

# WebApp menyu URL
_RENDER_URL = os.getenv("RENDER_URL", "https://fast-food-1-p4bx.onrender.com")
MENU_WEBAPP_URL = f"{_RENDER_URL}/webapp/menu.html"


def get_language_keyboard() -> ReplyKeyboardMarkup:
    """Til tanlash klaviaturasi — /start bosilganda chiqadi."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add(
        KeyboardButton("🇺🇿 O'zbek"),
        KeyboardButton("🇷🇺 Русский"),
        KeyboardButton("🇬🇧 English"),
    )
    return markup


def get_main_menu(lang: str = "uz"):
    """Eski funksiya — mavjud kod bilan moslik uchun saqlanadi."""
    return get_user_main_menu(lang)


def get_contact_keyboard(lang: str = "uz"):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        KeyboardButton(get_text("btn_send_phone", lang), request_contact=True),
        KeyboardButton(get_text("btn_cancel", lang))
    )
    return markup


def get_user_main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Oddiy foydalanuvchi uchun asosiy menyu."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton(get_text("btn_menu", lang)),
        KeyboardButton(get_text("btn_cart", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_search", lang)),
        KeyboardButton(get_text("btn_favorites", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_orders", lang)),
        KeyboardButton(get_text("btn_profile", lang)),
    )
    # ── WebApp interaktiv menyu tugmasi ──────────────────────────────
    markup.add(
        KeyboardButton(
            get_text("btn_web_menu", lang),
            web_app=WebAppInfo(url=f"{MENU_WEBAPP_URL}?lang={lang}")
        ),
    )
    markup.add(
        KeyboardButton(get_text("btn_contact", lang)),
    )
    return markup


def get_admin_main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Admin uchun asosiy menyu."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton(get_text("btn_menu", lang)),
        KeyboardButton(get_text("btn_cart", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_admin_menu", lang)),
        KeyboardButton(get_text("btn_menu_management", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_search", lang)),
        KeyboardButton(get_text("btn_favorites", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_orders", lang)),
        KeyboardButton(get_text("btn_profile", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_contact", lang)),
    )
    return markup
