from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from utils.i18n import get_text


def get_admin_keyboard(lang: str = "uz"):
    """Admin panel tugmalari — tanlangan tilda."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton(get_text("btn_orders_admin", lang)),
        KeyboardButton(get_text("btn_stats", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_broadcast", lang)),
        KeyboardButton(get_text("btn_add_product", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_promo_codes", lang)),
        KeyboardButton(get_text("btn_csv_report", lang)),
    )
    markup.add(KeyboardButton(get_text("btn_back_main", lang)))
    return markup


# ── Dinamik menyu admin klaviaturalari ───────────────────────────────────────

def get_dynamic_menu_admin_keyboard(lang: str = "uz"):
    """Admin uchun dinamik menyu boshqaruv klaviaturasi — tanlangan tilda."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton(get_text("btn_dm_add", lang)),
        KeyboardButton(get_text("btn_dm_price", lang)),
    )
    markup.add(
        KeyboardButton(get_text("btn_dm_delete", lang)),
        KeyboardButton(get_text("btn_dm_view", lang)),
    )
    markup.add(KeyboardButton(get_text("btn_back", lang)))
    return markup


def get_items_inline_keyboard(items: list, action: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Taomlar ro'yxatidan inline klaviatura yaratadi — tanlangan tilda."""
    markup = InlineKeyboardMarkup(row_width=1)
    for item in items:
        from utils.i18n import get_text as gt
        label = gt("search_item_label", lang, icon="🍴", name=item['name'], price=item['price'])
        callback = f"dm_{action}_{item['id']}"
        markup.add(InlineKeyboardButton(label, callback_data=callback))
    markup.add(InlineKeyboardButton(get_text("btn_cancel_inline", lang), callback_data="dm_cancel"))
    return markup


# ── Buyurtma holati tugmalari ────────────────────────────────────────────────

STATUS_LABELS = {
    "pending":    "⏳ Kutilmoqda",
    "preparing":  "🍳 Tayyorlanmoqda",
    "delivering": "🚗 Yetkazilmoqda",
    "completed":  "✅ Tugallandi",
    "cancelled":  "❌ Bekor qilingan",
}

STATUS_KEYS = {
    "pending":    "status_pending",
    "preparing":  "status_preparing",
    "delivering": "status_delivering",
    "completed":  "status_completed",
    "cancelled":  "status_cancelled",
}


def get_status_label(status: str, lang: str = "uz") -> str:
    """Buyurtma holati matnini tanlangan tilda qaytaradi."""
    key = STATUS_KEYS.get(status)
    if key:
        return get_text(key, lang)
    return STATUS_LABELS.get(status, f"⏳ {status}")


def get_order_status_keyboard(order_id: int, current_status: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Buyurtma holatini o'zgartirish uchun inline tugmalar — tanlangan tilda."""
    markup = InlineKeyboardMarkup(row_width=2)
    statuses = ["pending", "preparing", "delivering", "completed", "cancelled"]
    for s in statuses:
        if s == current_status:
            continue
        markup.insert(InlineKeyboardButton(
            get_status_label(s, lang),
            callback_data=f"adm_ordstatus_{order_id}_{s}"
        ))
    markup.add(InlineKeyboardButton(get_text("btn_orders_back", lang), callback_data="adm_orders_back"))
    return markup
