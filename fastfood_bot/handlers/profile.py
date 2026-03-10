from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from database.crud import get_user_orders, get_user, update_user_phone
from keyboards.main_menu import get_main_menu, get_contact_keyboard

class ProfileStates(StatesGroup):
    waiting_for_phone = State()

async def show_profile(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)
    
    if user and user['phone_number']:
        # User is fully registered
        text = (
            "👤 **Sizning profilingiz:**\n\n"
            f"👤 Ism: {user['full_name']}\n"
            f"📱 Telefon: {user['phone_number']}\n"
            f"🆔 ID: {user_id}\n"
        )
        if user['username']:
            text += f"🔗 Username: @{user['username']}\n"
            
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    else:
        # User needs to register phone number
        await message.answer(
            "Profil ma'lumotlaringizni to'liq ko'rish uchun telefon raqamingizni yuboring:",
            reply_markup=get_contact_keyboard()
        )
        await ProfileStates.waiting_for_phone.set()

async def process_contact(message: types.Message, state: FSMContext):
    if message.contact:
        phone_number = message.contact.phone_number
        user_id = message.from_user.id
        
        await update_user_phone(user_id, phone_number)
        await state.finish()
        
        await message.answer(
            "✅ Telefon raqamingiz muvaffaqiyatli saqlandi! Endi profilingizdan to'liq foydalanishingiz mumkin.",
            reply_markup=get_main_menu()
        )
        # Show the profile after saving
        await show_profile(message, state)
    elif message.text == "❌ Bekor qilish":
        await state.finish()
        await message.answer("Jarayon bekor qilindi.", reply_markup=get_main_menu())
    else:
        await message.answer(
            "Iltimos, pastdagi tugmani bosib telefon raqamingizni yuboring:",
            reply_markup=get_contact_keyboard()
        )

async def show_my_orders(message: types.Message):
    user_id = message.from_user.id
    orders = await get_user_orders(user_id)
    
    if not orders:
        await message.answer("Sizda hali buyurtmalar yo'q.")
        return

    text = "📦 **Sizning oxirgi buyurtmalaringiz:**\n\n"
    for order in orders:
        status_emoji = "✅" if order['status'] == 'completed' else "⏳"
        text += (
            f"🆔 Sizning {order['id']}-buyurtmangiz\n"
            f"📅 Sana: {order['created_at'].strftime('%Y-%m-%d %H:%M') if hasattr(order['created_at'], 'strftime') else order['created_at']}\n"
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
    dp.register_message_handler(show_profile, text="👤 Profil", state="*")
    dp.register_message_handler(process_contact, content_types=types.ContentTypes.CONTACT, state=ProfileStates.waiting_for_phone)
    dp.register_message_handler(process_contact, state=ProfileStates.waiting_for_phone)
    dp.register_message_handler(show_my_orders, text="📦 Buyurtmalarim")
    dp.register_message_handler(contact_us, text="☎️ Biz bilan aloqa")
