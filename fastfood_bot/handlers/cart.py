from aiogram import types, Dispatcher
from database.crud import add_to_cart, get_cart_items, clear_cart, remove_from_cart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode

async def add_item_to_cart_handler(call: types.CallbackQuery):
    # data: add_to_cart_{id}_{quantity}
    parts = call.data.split("_")
    product_id = int(parts[3])
    quantity = int(parts[4])
    
    await add_to_cart(call.from_user.id, product_id, quantity)
    await call.answer(f"{quantity} ta mahsulot savatga qo'shildi!", show_alert=True)


async def view_cart(message: types.Message):
    user_id = message.from_user.id
    items = await get_cart_items(user_id)
    
    if not items:
        await message.answer("Savat bo'sh 🛒")
        return
    
    total_price = 0
    text = "🛒 **Savat**\n\n"
    
    markup = InlineKeyboardMarkup()
    
    for item in items:
        item_total = item['price'] * item['quantity']
        total_price += item_total
        text += f"▫️ {item['name']} x {item['quantity']} = {item_total:,} so'm\n"
        markup.add(
            InlineKeyboardButton(f"❌ {item['name']} ni o'chirish", callback_data=f"del_cart_{item['id']}")
        )
        
    text += f"\n💰 **Jami: {total_price:,} so'm**"
    
    markup.add(
        InlineKeyboardButton("✅ Buyurtma berish", callback_data="checkout"),
        InlineKeyboardButton("🗑 Savatni tozalash", callback_data="clear_cart")
    )
    
    await message.answer(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

async def delete_cart_item(call: types.CallbackQuery):
    item_id = int(call.data.split("_")[2])
    await remove_from_cart(item_id)
    await call.answer("Mahsulot o'chirildi")
    # Refresh cart view (simplification: just send new message or edit)
    # Ideally edit, but for now we can just call view_cart with message object mock or edit text
    # Let's try to re-render. Since view_cart expects message, we need to adapt.
    # Simpler: just delete the message and send new cart view?
    # Or just edit the text.
    await call.message.delete()
    # Mocking message to reuse view_cart functionality
    await view_cart(call.message)

async def clear_cart_handler(call: types.CallbackQuery):
    await clear_cart(call.from_user.id)
    await call.answer("Savat tozalandi")
    await call.message.edit_text("Savat bo'sh 🛒")

def register_cart_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(add_item_to_cart_handler, lambda c: c.data.startswith('add_to_cart_'))
    dp.register_message_handler(view_cart, text="🛒 Savat")
    dp.register_callback_query_handler(delete_cart_item, lambda c: c.data.startswith('del_cart_'))
    dp.register_callback_query_handler(clear_cart_handler, text="clear_cart")
