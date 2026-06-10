from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.i18n import get_text


def get_categories_markup(categories, lang="uz"):
    markup = InlineKeyboardMarkup(row_width=2)
    for category in categories:
        markup.insert(
            InlineKeyboardButton(
                text=f"{category['emoji'] or '🍽'} {category['name']}",
                callback_data=f"category_{category['id']}"
            )
        )
    return markup


def get_product_markup(product_id, category_id, current_index, total_products,
                       quantity=1, is_favorite=False, lang="uz"):
    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton("➖", callback_data=f"minus_{product_id}_{quantity}_{category_id}_{current_index}"),
        InlineKeyboardButton(get_text("qty_label", lang, qty=quantity), callback_data="noop"),
        InlineKeyboardButton("➕", callback_data=f"plus_{product_id}_{quantity}_{category_id}_{current_index}")
    )
    markup.row(
        InlineKeyboardButton(
            text=get_text("btn_add_to_cart", lang),
            callback_data=f"add_to_cart_{product_id}_{quantity}"
        ),
        InlineKeyboardButton(
            text="💔" if is_favorite else "❤️",
            callback_data=f"fav_{product_id}_{category_id}_{current_index}"
        )
    )

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(
            InlineKeyboardButton("⬅️", callback_data=f"paginate_{category_id}_{current_index - 1}")
        )
    if current_index < total_products - 1:
        nav_buttons.append(
            InlineKeyboardButton("➡️", callback_data=f"paginate_{category_id}_{current_index + 1}")
        )
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(
        InlineKeyboardButton(
            text=get_text("btn_back_to_categories", lang),
            callback_data="back_to_categories"
        )
    )
    return markup


# ── Admin uchun alohida markup ──────────────────────────────────────

def get_admin_categories_markup(categories):
    """Admin kategoriyalar — admin_cat_ prefiksi bilan."""
    markup = InlineKeyboardMarkup(row_width=2)
    for category in categories:
        markup.insert(
            InlineKeyboardButton(
                text=f"{category['emoji'] or '🍽'} {category['name']}",
                callback_data=f"admin_cat_{category['id']}"
            )
        )
    return markup


def get_admin_product_markup(product_id, category_id, current_index,
                              total_products, is_active=True, has_discount=False):
    """Admin mahsulot sahifasi — boshqaruv tugmalari bilan."""
    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton("💰 Narx", callback_data=f"admin_price_{product_id}"),
        InlineKeyboardButton("🖼 Rasm", callback_data=f"admin_image_{product_id}"),
    )
    markup.row(
        InlineKeyboardButton(
            "🏷 Chegirmani olish" if has_discount else "🏷 Chegirma",
            callback_data=f"admin_discount_{product_id}"
        ),
        InlineKeyboardButton(
            "👁 Ko'rsatish" if not is_active else "🙈 Yashirish",
            callback_data=f"admin_toggle_{product_id}"
        ),
    )

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(
            InlineKeyboardButton("⬅️", callback_data=f"admin_paginate_{category_id}_{current_index - 1}")
        )
    if current_index < total_products - 1:
        nav_buttons.append(
            InlineKeyboardButton("➡️", callback_data=f"admin_paginate_{category_id}_{current_index + 1}")
        )
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(
        InlineKeyboardButton(
            text="⬅️ Kategoriyalarga qaytish",
            callback_data="admin_back_to_cats"
        )
    )
    return markup
