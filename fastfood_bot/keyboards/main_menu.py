from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🍽 Menu"),
        KeyboardButton("🛒 Savat"),
        KeyboardButton("👤 Profil"),
        KeyboardButton("📦 Buyurtmalarim"),
        KeyboardButton("☎️ Biz bilan aloqa")
    )
    return markup
