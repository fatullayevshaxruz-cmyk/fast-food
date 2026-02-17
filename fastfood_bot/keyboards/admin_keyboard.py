from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📢 Xabar tarqatish"),
        KeyboardButton("📊 Statistika"),
        KeyboardButton("➕ Mahsulot qo'shish"),
        KeyboardButton("⬅️ Asosiy menu")
    )
    return markup
