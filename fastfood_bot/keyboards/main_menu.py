from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu():
    """Eski funksiya — mavjud kod bilan moslik uchun saqlanadi."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🍽 Menu"),
        KeyboardButton("🛒 Savat"),
        KeyboardButton("📦 Buyurtmalarim"),
        KeyboardButton("☎️ Biz bilan aloqa")
    )
    return markup


def get_contact_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True),
        KeyboardButton("❌ Bekor qilish")
    )
    return markup


# ── Dinamik menyu uchun yangi klaviaturalar ──────────────────────────────────

def get_user_main_menu() -> ReplyKeyboardMarkup:
    """Oddiy foydalanuvchi uchun asosiy menyu."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🍽 Menu"),
        KeyboardButton("🛒 Savat"),
    )
    markup.add(
        KeyboardButton("🛠 Admin menu"),
        KeyboardButton("📦 Buyurtmalarim"),
    )
    markup.add(
        KeyboardButton("☎️ Biz bilan aloqa")
    )
    return markup


def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Admin uchun asosiy menyu."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🍽 Menu"),
        KeyboardButton("🛒 Savat"),
    )
    markup.add(
        KeyboardButton("🛠 Admin menu"),
        KeyboardButton("📦 Buyurtmalarim"),
    )
    markup.add(
        KeyboardButton("🛠 Menyu boshqaruvi"),
        KeyboardButton("☎️ Biz bilan aloqa"),
    )
    return markup
