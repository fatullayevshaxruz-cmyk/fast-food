from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_categories_markup(categories):
    markup = InlineKeyboardMarkup(row_width=2)
    for category in categories:
        # category is a Record object from asyncpg
        markup.insert(
            InlineKeyboardButton(
                text=f"{category['emoji'] or '🍽'} {category['name']}",
                callback_data=f"category_{category['id']}"
            )
        )
    return markup

def get_product_markup(product_id, category_id, current_index, total_products, quantity=1):
    markup = InlineKeyboardMarkup()
    
    # Quantity controls
    # callback: action_productid_quantity_catid_index
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

    # Navigation Buttons
    nav_buttons = []
    # If not the first item, show Prev
    if current_index > 0:
         nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"paginate_{category_id}_{current_index - 1}"))
    
    # Pagination info (center) - Optional, or just Prev/Next
    # nav_buttons.append(InlineKeyboardButton(f"{current_index + 1}/{total_products}", callback_data="noop"))

    # If not the last item, show Next
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

