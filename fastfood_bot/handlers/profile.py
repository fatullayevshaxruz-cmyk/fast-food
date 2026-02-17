from aiogram import types, Dispatcher
from database.crud import get_user_orders
from aiogram.types import ParseMode

async def show_my_orders(message: types.Message):
    user_id = message.from_user.id
    orders = await get_user_orders(user_id)
    
    if not orders:
        await message.answer("Sizda hali buyurtmalar yo'q.")
        return

    text = "📦 **Sizning oxirgi buyurtmalaringiz:**\n\n"
    for order in orders:
        # Format date (assuming created_at is timestamp or string)
        # Simplify display
        status_emoji = "✅" if order['status'] == 'completed' else "⏳"
        text += (
            f"🆔 Sizning {order['id']}-buyurtmangiz\n"
            f"📅 Sana: {order['created_at']}\n"
            f"💰 Summa: {order['total_amount']:,} so'm\n"
            f"Stauts: {status_emoji} {order['status']}\n"
            f"-------------------\n"
        )
        
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

async def contact_us(message: types.Message):
    contact_text = (
        "📞 **Biz bilan bog'lanish:**\n\n"
        "Agar savollaringiz yoki takliflaringiz bo'lsa, quyidagi raqamga qo'ng'iroq qiling:\n\n"
        "📞 **+998943265755**"
    )
    await message.answer(contact_text, parse_mode=ParseMode.MARKDOWN)

def register_profile_handlers(dp: Dispatcher):
    dp.register_message_handler(show_my_orders, text="📦 Buyurtmalarim")
    dp.register_message_handler(contact_us, text="☎️ Biz bilan aloqa")
