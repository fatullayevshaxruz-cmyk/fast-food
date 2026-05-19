from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_keyboard():
    """Admin panel tugmalari."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📦 Buyurtmalar"),
        KeyboardButton("📊 Statistika"),
    )
    markup.add(
        KeyboardButton("📢 Xabar tarqatish"),
        KeyboardButton("➕ Mahsulot qo'shish"),
    )
    markup.add(
        KeyboardButton("🎟 Promo kodlar"),
        KeyboardButton("📥 Hisobot (CSV)"),
    )
    markup.add(KeyboardButton("⬅️ Asosiy menu"))
    return markup


# ── Dinamik menyu admin klaviaturalari ───────────────────────────────────────

def get_dynamic_menu_admin_keyboard():
    """Admin uchun dinamik menyu boshqaruv klaviaturasi."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("➕ Taom qo'shish"),
        KeyboardButton("💰 Narx o'zgartirish"),
    )
    markup.add(
        KeyboardButton("🗑 Taomni o'chirish"),
        KeyboardButton("📝 Menyuni ko'rish"),
    )
    markup.add(KeyboardButton("⬅️ Orqaga"))
    return markup


def get_items_inline_keyboard(items: list, action: str) -> InlineKeyboardMarkup:
    """Taomlar ro'yxatidan inline klaviatura yaratadi."""
    markup = InlineKeyboardMarkup(row_width=1)
    for item in items:
        label = f"🍴 {item['name']}  —  {item['price']:,} so'm"
        callback = f"dm_{action}_{item['id']}"
        markup.add(InlineKeyboardButton(label, callback_data=callback))
    markup.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="dm_cancel"))
    return markup


# ── Buyurtma holati tugmalari ────────────────────────────────────────────────

STATUS_LABELS = {
    "pending":    "⏳ Kutilmoqda",
    "preparing":  "🍳 Tayyorlanmoqda",
    "delivering": "🚗 Yetkazilmoqda",
    "completed":  "✅ Tugallandi",
    "cancelled":  "❌ Bekor qilingan",
}

def get_order_status_keyboard(order_id: int, current_status: str) -> InlineKeyboardMarkup:
    """Buyurtma holatini o'zgartirish uchun inline tugmalar."""
    markup = InlineKeyboardMarkup(row_width=2)
    statuses = ["pending", "preparing", "delivering", "completed", "cancelled"]
    for s in statuses:
        if s == current_status:
            continue
        markup.insert(InlineKeyboardButton(
            STATUS_LABELS[s],
            callback_data=f"adm_ordstatus_{order_id}_{s}"
        ))
    markup.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_orders_back"))
    return markup
