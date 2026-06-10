from aiogram import types, Dispatcher
from database.crud import add_to_cart, get_cart_items, clear_cart, remove_from_cart, get_user_language
from utils.i18n import get_text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


async def add_item_to_cart_handler(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    parts = call.data.split("_")
    product_id = int(parts[3])
    quantity = int(parts[4])

    await add_to_cart(call.from_user.id, product_id, quantity)
    await call.answer(get_text("cart_item_added", lang, qty=quantity), show_alert=True)

    markup = call.message.reply_markup
    if markup:
        has_cart_btn = False
        if markup.inline_keyboard:
            has_cart_btn = any(
                btn.callback_data == "go_to_cart"
                for row in markup.inline_keyboard
                for btn in row
            )

        if not has_cart_btn:
            markup.add(InlineKeyboardButton(
                get_text("btn_go_to_cart", lang),
                callback_data="go_to_cart"
            ))
            try:
                await call.message.edit_reply_markup(reply_markup=markup)
            except Exception:
                pass


async def go_to_cart_handler(call: types.CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    user_id = call.from_user.id
    await _show_cart(call.message, user_id)


async def view_cart(message: types.Message):
    user_id = message.from_user.id
    await _show_cart(message, user_id)


async def _show_cart(message, user_id):
    """Savat ko'rsatish — umumiy funksiya."""
    from config import DELIVERY_FEE, MIN_ORDER_AMOUNT
    lang = await get_user_language(user_id)
    items = await get_cart_items(user_id)

    if not items:
        await message.answer(get_text("cart_is_empty", lang))
        return

    total_price = 0
    text = get_text("cart_title", lang) + "\n\n"

    markup = InlineKeyboardMarkup()

    for item in items:
        item_total = item['price'] * item['quantity']
        total_price += item_total
        if lang == "ru":
            text += f"  ▫️ {item['name']} x {item['quantity']} = {item_total:,} сум\n"
        elif lang == "en":
            text += f"  ▫️ {item['name']} x {item['quantity']} = {item_total:,} sum\n"
        else:
            text += f"  ▫️ {item['name']} x {item['quantity']} = {item_total:,} so'm\n"

        markup.add(InlineKeyboardButton(
            get_text("cart_remove_item", lang, name=item['name']),
            callback_data=f"del_cart_{item['id']}_{user_id}"
        ))

    text += f"\n{get_text('cart_products_total', lang, total=total_price)}\n"
    text += "  ━━━━━━━━━━━━━━━\n"
    text += get_text("cart_dine_in_line", lang, price=total_price) + "\n"
    text += get_text("cart_delivery_line", lang, price=total_price + DELIVERY_FEE, fee=DELIVERY_FEE) + "\n"

    if total_price < MIN_ORDER_AMOUNT:
        diff = MIN_ORDER_AMOUNT - total_price
        text += get_text("cart_min_order_note", lang, min=MIN_ORDER_AMOUNT, diff=diff)

    markup.add(
        InlineKeyboardButton(get_text("btn_checkout", lang), callback_data="checkout"),
        InlineKeyboardButton(get_text("btn_clear_cart", lang), callback_data="confirm_clear_cart")
    )

    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def delete_cart_item(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    parts = call.data.split("_")
    item_id = int(parts[2])
    user_id = int(parts[3])

    await remove_from_cart(item_id)
    await call.answer(get_text("item_removed", lang))

    try:
        await call.message.delete()
    except Exception:
        pass

    await _show_cart(call.message, user_id)


async def confirm_clear_cart(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(get_text("btn_yes_clear", lang), callback_data="clear_cart_yes"),
        InlineKeyboardButton(get_text("btn_no", lang), callback_data="clear_cart_no")
    )
    await call.message.edit_text(
        get_text("confirm_clear_cart", lang),
        reply_markup=markup,
        parse_mode="HTML"
    )
    await call.answer()


async def clear_cart_yes(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    await clear_cart(call.from_user.id)
    await call.answer(get_text("cart_cleared", lang))
    await call.message.edit_text(get_text("cart_cleared", lang))


async def clear_cart_no(call: types.CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await _show_cart(call.message, call.from_user.id)


def register_cart_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(add_item_to_cart_handler, lambda c: c.data.startswith('add_to_cart_'))
    dp.register_callback_query_handler(go_to_cart_handler, text="go_to_cart")
    _CART_TEXTS = ["🛒 Savat", "🛒 Корзина", "🛒 Cart"]
    dp.register_message_handler(view_cart, lambda m: m.text in _CART_TEXTS)
    dp.register_callback_query_handler(delete_cart_item, lambda c: c.data.startswith('del_cart_'))
    dp.register_callback_query_handler(confirm_clear_cart, text="confirm_clear_cart")
    dp.register_callback_query_handler(clear_cart_yes, text="clear_cart_yes")
    dp.register_callback_query_handler(clear_cart_no, text="clear_cart_no")
