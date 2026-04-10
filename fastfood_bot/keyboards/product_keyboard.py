from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_categories_markup(categories):
    markup = InlineKeyboardMarkup(row_width=2)
    for category in categories:
        markup.insert(
            InlineKeyboardButton(
                text=f"{category['emoji'] or '🍽'} {category['name']}",
                callback_data=f"category_{category['id']}"
            )
        )
    return markup


def get_product_markup(product_id, category_id, current_index, total_products, quantity=1):
    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton("➖", callback_data=f"minus_{product_id}_{quantity}_{category_id}_{current_index}"),
        InlineKeyboardButton(f"{quantity} dona", callback_data="noop"),
        InlineKeyboardButton("➕", callback_data=f"plus_{product_id}_{quantity}_{category_id}_{current_index}")
    )
    markup.add(
        InlineKeyboardButton(
            text="🛒 Savatga qo'shish",
            callback_data=f"add_to_cart_{product_id}_{quantity}"
        )
    )

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"paginate_{category_id}_{current_index - 1}"))
    if current_index < total_products - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"paginate_{category_id}_{current_index + 1}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(
        InlineKeyboardButton(
            text="⬅️ Kategoriyalarga qaytish",
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


def get_admin_product_markup(product_id, category_id, current_index, total_products):
    """Admin mahsulot sahifasi — 'Savatga qo'shish' o'rniga 'Narx o'zgartirish'."""
    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            text="💰 Narx o'zgartirish",
            callback_data=f"admin_price_{product_id}"
        )
    )

    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"admin_paginate_{category_id}_{current_index - 1}"))
    if current_index < total_products - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"admin_paginate_{category_id}_{current_index + 1}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    markup.add(
        InlineKeyboardButton(
            text="⬅️ Kategoriyalarga qaytish",
            callback_data="admin_back_to_cats"
        )
    )
    return markup
