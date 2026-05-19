from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu():
    """Eski funksiya — mavjud kod bilan moslik uchun saqlanadi."""
    return get_user_main_menu()


def get_contact_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True),
        KeyboardButton("❌ Bekor qilish")
    )
    return markup


def get_user_main_menu() -> ReplyKeyboardMarkup:
    """Oddiy foydalanuvchi uchun asosiy menyu."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🍽 Menu"),
        KeyboardButton("🛒 Savat"),
    )
    markup.add(
        KeyboardButton("🔍 Izlash"),
        KeyboardButton("❤️ Sevimlilar"),
    )
    markup.add(
        KeyboardButton("📦 Buyurtmalarim"),
        KeyboardButton("👤 Profil"),
    )
    markup.add(
        KeyboardButton("☎️ Biz bilan aloqa"),
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
        KeyboardButton("🛠 Menyu boshqaruvi"),
    )
    markup.add(
        KeyboardButton("🔍 Izlash"),
        KeyboardButton("❤️ Sevimlilar"),
    )
    markup.add(
        KeyboardButton("📦 Buyurtmalarim"),
        KeyboardButton("👤 Profil"),
    )
    markup.add(
        KeyboardButton("☎️ Biz bilan aloqa"),
    )
    return markup
