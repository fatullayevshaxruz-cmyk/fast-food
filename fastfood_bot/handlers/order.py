from aiogram import types, Dispatcher
import asyncio
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ContentTypes
from database.crud import get_cart_items, create_order, add_order_items, clear_cart
from utils.states import OrderStates
from keyboards.main_menu import get_main_menu
from utils.helpers import notify_admins_new_order


async def start_checkout(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    items = await get_cart_items(user_id)
    if not items:
        await call.answer("Savatingiz bo'sh!", show_alert=True)
        return

    print(f"DEBUG: start_checkout called for {user_id}. Setting state to waiting_for_location.")
    await OrderStates.waiting_for_delivery_type.set()
    print("DEBUG: State set to waiting_for_delivery_type.")
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🏠 Shu yerda"), KeyboardButton("🛵 Olib ketish"))
    markup.add(KeyboardButton("❌ Bekor qilish"))
    
    await call.message.answer("Ajoyib! Buyurtmani qanday usulda qabul qilasiz?", reply_markup=markup)
    await call.answer()

async def process_delivery_type(message: types.Message, state: FSMContext):
    if message.text == "🏠 Shu yerda":
        await state.update_data(delivery_type="eat_in")
        await OrderStates.waiting_for_table_number.set()
        
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(KeyboardButton("❌ Bekor qilish"))
        await message.answer("Iltimos, stol raqamini kiriting (Masalan: 12):", reply_markup=markup)
        
    elif message.text == "🛵 Olib ketish":
        await state.update_data(delivery_type="delivery")
        await OrderStates.waiting_for_location.set()
        
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(KeyboardButton("📍 Joylashuvni yuborish", request_location=True))
        markup.add(KeyboardButton("❌ Bekor qilish"))
        
        await message.answer("Iltimos, yetkazib berish manzilini yuboring yoki lokatsiyangizni ulashing.", reply_markup=markup)
    else:
        await message.answer("Iltimos, pastdagi tugmalardan birini tanlang.")

async def process_table_number(message: types.Message, state: FSMContext):
    table_num = message.text
    # Save table number in address format for easy reuse
    await state.update_data(address=f"Stol raqami: {table_num}", lat=None, lon=None)
    
    await OrderStates.waiting_for_phone.set()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    markup.add(KeyboardButton("❌ Bekor qilish"))
    
    await message.answer("Bog'lanish uchun telefon raqamingizni yuboring:", reply_markup=markup)

async def cancel_order(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Buyurtma bekor qilindi.", reply_markup=get_main_menu())

async def process_location(message: types.Message, state: FSMContext):
    try:
        # Check if message is a command or menu button
        if message.text and (message.text.startswith("/") or message.text in ["🍽 Menu", "🛒 Savat", "ℹ️ Biz haqimizda", "📞 Bog'lanish"]):
            await state.finish()
            await message.answer("Buyurtma jarayoni bekor qilindi. Iltimos, menudan foydalaning.", reply_markup=get_main_menu())
            return

        lat, lon, address = None, None, None

        if message.location:
            lat = message.location.latitude
            lon = message.location.longitude
            address = f"Lat: {lat}, Lon: {lon}"
        elif message.venue:
            lat = message.venue.location.latitude
            lon = message.venue.location.longitude
            address = message.venue.address or message.venue.title
        else:
            address = message.text
            
        await state.update_data(address=address, lat=lat, lon=lon)

        await OrderStates.waiting_for_phone.set()
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
        markup.add(KeyboardButton("❌ Bekor qilish"))
        
        await message.answer("Bog'lanish uchun telefon raqamingizni yuboring:", reply_markup=markup)
    except Exception as e:
        import traceback
        traceback.print_exc()
        await message.answer(f"Xatolik yuz berdi: {e}")


async def process_phone(message: types.Message, state: FSMContext):
    try:
        print(f"DEBUG: process_phone triggered. Content: {message.content_type}")
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = message.text
            
        await state.update_data(phone=phone)
        
        # Skip payment selection, go directly to finish
        await finish_order(message, state)
    except Exception as e:
        print(f"ERROR in process_phone: {e}")
        await message.answer(f"Xatolik yuz berdi: {e}")


async def finish_order(message: types.Message, state: FSMContext):
    try:
        print("DEBUG: finish_order started.")
        data = await state.get_data()
        user_id = message.from_user.id
        phone = data.get('phone')
        address = data.get('address')
        lat = data.get('lat')
        lon = data.get('lon')
        
        # Calculate Total
        items = await get_cart_items(user_id)
        if not items:
            await message.answer("Savat bo'shab qoldi!", reply_markup=get_main_menu())
            await state.finish()
            return
    
        total_amount = sum(item['price'] * item['quantity'] for item in items)
        
        print("DEBUG: Creating order in DB...")
        # Create Order in DB (Default to 'cash' or 'pay_on_delivery')
        order_id = await create_order(
            user_id=user_id,
            total_amount=total_amount,
            address=address,
            payment_method="Naqd (Yetkazib berilganda)",
            latitude=lat,
            longitude=lon,
            phone_number=phone
        )
        print(f"DEBUG: Order created with ID: {order_id}")
        
        # Add items
        await add_order_items(order_id, items)
        
        # Clear Cart
        await clear_cart(user_id)
        
        # Create receipt text
        receipt_text = ""
        for item in items:
            item_total = item['price'] * item['quantity']
            receipt_text += f"▫️ {item['name']} x {item['quantity']} = {item_total:,} so'm\n"
    
        await state.finish()
        
        print("DEBUG: Notifying admins (Background Task)...")
        # Run notification in background to avoid blocking the user response
        asyncio.create_task(notify_admins_new_order(
            bot=message.bot,
            order_id=order_id,
            total_amount=total_amount,
            user=message.from_user,
            items=items,
            phone=phone,
            address=address,
            location={'lat': lat, 'lon': lon}
        ))
        
        await message.answer(
            f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"🛵 Yetkazib beruvchimiz manzilingizga yetib borganda siz bilan bog'lanadi.\n\n"
            f"💴 <b>To'lov miqdori: {total_amount:,} so'm</b>\n"
            f"<i>(To'lovni mahsulotni qabul qilib olganda to'laysiz)</i>\n\n"
            "Bizni tanlaganingiz uchun rahmat! Yoqimli ishtaha! 😋",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR in finish_order: {e}")
        await message.answer(f"Buyurtmani yakunlashda xatolik: {e}")





async def debug_location_state(message: types.Message, state: FSMContext):
    print(f"DEBUG: CATCH-ALL in waiting_for_location. ContentType: {message.content_type}, Text: {message.text}")
    await message.answer(f"DEBUG: Men sizni eshityapman, lekin type noto'g'ri: {message.content_type}")

def register_order_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(start_checkout, text="checkout")
    dp.register_message_handler(cancel_order, text="❌ Bekor qilish", state="*")
    dp.register_message_handler(process_delivery_type, state=OrderStates.waiting_for_delivery_type)
    dp.register_message_handler(process_table_number, state=OrderStates.waiting_for_table_number)
    dp.register_message_handler(process_location, content_types=['location', 'venue', 'text'], state=OrderStates.waiting_for_location)
    dp.register_message_handler(process_phone, content_types=['contact', 'text'], state=OrderStates.waiting_for_phone)
