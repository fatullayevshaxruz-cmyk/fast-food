from aiogram import types, Dispatcher
from database.crud import add_to_cart, get_cart_items, clear_cart, remove_from_cart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode


async def add_item_to_cart_handler(call: types.CallbackQuery):
    parts = call.data.split("_")
    product_id = int(parts[3])
    quantity = int(parts[4])
    
    await add_to_cart(call.from_user.id, product_id, quantity)
    await call.answer(f"✅ {quantity} ta mahsulot savatga qo'shildi!", show_alert=True)
    
    markup = call.message.reply_markup
    if markup:
        has_cart_btn = False
        if markup.inline_keyboard:
            has_cart_btn = any(btn.callback_data == "go_to_cart" for row in markup.inline_keyboard for btn in row)
        
        if not has_cart_btn:
            markup.add(InlineKeyboardButton("🛒 Savatga o'tish", callback_data="go_to_cart"))
            try:
                await call.message.edit_reply_markup(reply_markup=markup)
            except Exception:
                pass


async def go_to_cart_handler(call: types.CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    
    # call.from_user.id dan foydalanamiz (call.message.from_user emas!)
    user_id = call.from_user.id
    await _show_cart(call.message, user_id)


async def view_cart(message: types.Message):
    user_id = message.from_user.id
    await _show_cart(message, user_id)


async def _show_cart(message, user_id):
    """Savat ko'rsatish — umumiy funksiya."""
    from config import DELIVERY_FEE, MIN_ORDER_AMOUNT
    items = await get_cart_items(user_id)
    
    if not items:
        await message.answer("Savat bo'sh 🛒")
        return
    
    total_price = 0
    text = "🛒 <b>Savat</b>\n\n"
    
    markup = InlineKeyboardMarkup()
    
    for item in items:
        item_total = item['price'] * item['quantity']
        total_price += item_total
        text += f"  ▫️ {item['name']} x {item['quantity']} = {item_total:,} so'm\n"
        markup.add(
            InlineKeyboardButton(f"❌ {item['name']} ni o'chirish", callback_data=f"del_cart_{item['id']}_{user_id}")
        )
        
    text += f"\n  💰 <b>Mahsulotlar: {total_price:,} so'm</b>\n"
    text += f"  ━━━━━━━━━━━━━━━\n"
    text += f"  🍽️ <b>Shu yerda:</b> {total_price:,} so'm <i>(yetkazish bepul)</i>\n"
    text += f"  🛵 <b>Yetkazib berish:</b> {total_price + DELIVERY_FEE:,} so'm <i>(+{DELIVERY_FEE:,} yetkazish)</i>\n"

    if total_price < MIN_ORDER_AMOUNT:
        diff = MIN_ORDER_AMOUNT - total_price
        text += f"\n  ⚠️ <i>Yetkazib berish uchun minimal: {MIN_ORDER_AMOUNT:,} so'm (yana {diff:,} so'm kerak)</i>\n"
    
    markup.add(
        InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout"),
        InlineKeyboardButton("🗑 Savatni tozalash", callback_data="confirm_clear_cart")
    )
    
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def delete_cart_item(call: types.CallbackQuery):
    parts = call.data.split("_")
    item_id = int(parts[2])
    user_id = int(parts[3])  # Saqlangan user_id
    
    await remove_from_cart(item_id)
    await call.answer("✅ Mahsulot o'chirildi")
    
    try:
        await call.message.delete()
    except Exception:
        pass
    
    await _show_cart(call.message, user_id)


async def confirm_clear_cart(call: types.CallbackQuery):
    """Savat tozalash tasdiqlash."""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ Ha, tozalash", callback_data="clear_cart_yes"),
        InlineKeyboardButton("❌ Yo'q", callback_data="clear_cart_no")
    )
    await call.message.edit_text(
        "⚠️ <b>Haqiqatan savatni tozalaysizmi?</b>\n"
        "Bu amalni ortga qaytarib bo'lmaydi!",
        reply_markup=markup,
        parse_mode="HTML"
    )
    await call.answer()


async def clear_cart_yes(call: types.CallbackQuery):
    await clear_cart(call.from_user.id)
    await call.answer("✅ Savat tozalandi")
    await call.message.edit_text("🛒 Savat tozalandi!")


async def clear_cart_no(call: types.CallbackQuery):
    """Bekor qilish — savatni qayta ko'rsatish."""
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await _show_cart(call.message, call.from_user.id)


def register_cart_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(add_item_to_cart_handler, lambda c: c.data.startswith('add_to_cart_'))
    dp.register_callback_query_handler(go_to_cart_handler, text="go_to_cart")
    # Savat tugmasi — 3 tilda
    _CART_TEXTS = ["🛒 Savat", "🛒 Корзина", "🛒 Cart"]
    dp.register_message_handler(view_cart, lambda m: m.text in _CART_TEXTS)
    dp.register_callback_query_handler(delete_cart_item, lambda c: c.data.startswith('del_cart_'))
    dp.register_callback_query_handler(confirm_clear_cart, text="confirm_clear_cart")
    dp.register_callback_query_handler(clear_cart_yes, text="clear_cart_yes")
    dp.register_callback_query_handler(clear_cart_no, text="clear_cart_no")
