from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import (
    get_user_orders, get_order_items_detail, get_order_by_id, get_user,
    get_favorites, repeat_order_to_cart, update_user_name, update_user_phone,
    update_user_address
)
from keyboards.admin_keyboard import STATUS_LABELS
from utils.states import ProfileStates


# ── Buyurtmalarim ────────────────────────────────────────────────────

async def show_my_orders(message: types.Message, user_id: int = None):
    if user_id is None:
        user_id = message.from_user.id
    orders = await get_user_orders(user_id)
    
    if not orders:
        await message.answer("📦 Sizda hali buyurtmalar yo'q.")
        return

    text = "📦 <b>Sizning buyurtmalaringiz:</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    
    for order in orders:
        status = order['status'] or 'pending'
        status_text = STATUS_LABELS.get(status, f"⏳ {status}")
        created = order['created_at']
        date_str = created.strftime('%Y-%m-%d %H:%M') if hasattr(created, 'strftime') else str(created)[:16] if created else "—"
        
        text += (
            f"📋 <b>#{order['id']}</b> | {status_text} | {order['total_amount']:,} so'm\n"
            f"   📅 {date_str}\n\n"
        )
        markup.add(InlineKeyboardButton(
            f"📋 #{order['id']} tafsilot",
            callback_data=f"myorder_{order['id']}"
        ))
        
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def show_order_detail(call: types.CallbackQuery):
    order_id = int(call.data.split("_")[1])
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi.", show_alert=True)
        return
    items = await get_order_items_detail(order_id)
    status = order['status'] or 'pending'
    status_text = STATUS_LABELS.get(status, f"⏳ {status}")
    created = order['created_at']
    date_str = created.strftime('%Y-%m-%d %H:%M') if hasattr(created, 'strftime') else str(created)[:16] if created else "—"
    
    text = (
        f"📋 <b>Buyurtma #{order['id']}</b>\n\n"
        f"📅 {date_str}\n"
        f"Holat: {status_text}\n"
        f"📍 {order['delivery_address'] or '—'}\n"
        f"📞 {order['phone_number'] or '—'}\n"
    )
    note = None
    try:
        note = order['note']
    except (KeyError, IndexError):
        pass
    if note:
        text += f"📝 <i>{note}</i>\n"
    
    text += "\n🍛 <b>Tarkibi:</b>\n"
    total = 0
    for item in items:
        item_total = item['price_at_time'] * item['quantity']
        total += item_total
        text += f"  ▫️ {item['name']} x {item['quantity']} = {item_total:,} so'm\n"
    text += f"\n💰 <b>Jami: {total:,} so'm</b>"
    
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🔄 Qaytadan buyurtma", callback_data=f"repeat_{order_id}"),
        InlineKeyboardButton("⬅️ Orqaga", callback_data="myorders_back")
    )
    
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await call.answer()


async def repeat_order_handler(call: types.CallbackQuery):
    """Oxirgi buyurtmani qaytadan savatga qo'shish."""
    order_id = int(call.data.split("_")[1])
    count = await repeat_order_to_cart(call.from_user.id, order_id)
    if count > 0:
        await call.answer(f"✅ {count} ta mahsulot savatga qo'shildi!", show_alert=True)
    else:
        await call.answer("Buyurtmada mahsulotlar topilmadi.", show_alert=True)


async def myorders_back(call: types.CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    await show_my_orders(call.message, user_id=call.from_user.id)
    await call.answer()


# ── Sevimlilar ───────────────────────────────────────────────────────

async def show_favorites(message: types.Message):
    user_id = message.from_user.id
    favs = await get_favorites(user_id)
    if not favs:
        await message.answer("❤️ Sevimlilar ro'yxati bo'sh.\n\nMahsulot kartochkasidagi ❤️ tugmasini bosib qo'shing!")
        return
    
    text = "❤️ <b>Sevimli mahsulotlaringiz:</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    for p in favs:
        old_price = None
        try:
            old_price = p['old_price']
        except (KeyError, IndexError):
            pass
        if old_price and old_price > p['price']:
            label = f"🏷 {p['name']} — {p['price']:,} so'm"
        else:
            label = f"🍴 {p['name']} — {p['price']:,} so'm"
        markup.add(InlineKeyboardButton(label, callback_data=f"search_prod_{p['id']}_{p['category_id']}"))
    
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


# ── Profil ───────────────────────────────────────────────────────────

async def show_profile(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer("Profil topilmadi. /start buyrug'ini yuboring.")
        return
    
    name = user['full_name'] or '—'
    phone = user['phone_number'] or '—'
    address = None
    try:
        address = user['default_address']
    except (KeyError, IndexError):
        pass
    address = address or '—'
    
    text = (
        f"👤 <b>Sizning profilingiz</b>\n\n"
        f"📛 Ism: <b>{name}</b>\n"
        f"📞 Telefon: <b>{phone}</b>\n"
        f"📍 Manzil: <b>{address}</b>\n"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("✏️ Ismni o'zgartirish", callback_data="edit_name"),
        InlineKeyboardButton("📞 Telefonni o'zgartirish", callback_data="edit_phone"),
        InlineKeyboardButton("📍 Manzilni o'zgartirish", callback_data="edit_address"),
    )
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def edit_name_start(call: types.CallbackQuery):
    await ProfileStates.editing_name.set()
    await call.message.answer("✏️ Yangi ismingizni yozing:")
    await call.answer()

async def edit_name_done(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Ism kamida 2 harf bo'lishi kerak.")
        return
    await update_user_name(message.from_user.id, name)
    await state.finish()
    await message.answer(f"✅ Ism o'zgartirildi: <b>{name}</b>", parse_mode="HTML")

async def edit_phone_start(call: types.CallbackQuery):
    await ProfileStates.editing_phone.set()
    await call.message.answer("📞 Yangi telefon raqamingizni yozing:")
    await call.answer()

async def edit_phone_done(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    await update_user_phone(message.from_user.id, phone)
    await state.finish()
    await message.answer(f"✅ Telefon o'zgartirildi: <b>{phone}</b>", parse_mode="HTML")

async def edit_address_start(call: types.CallbackQuery):
    await ProfileStates.editing_address.set()
    await call.message.answer("📍 Yangi manzilingizni yozing:")
    await call.answer()

async def edit_address_done(message: types.Message, state: FSMContext):
    address = message.text.strip()
    await update_user_address(message.from_user.id, address)
    await state.finish()
    await message.answer(f"✅ Manzil saqlandi: <b>{address}</b>", parse_mode="HTML")


# ── Aloqa ────────────────────────────────────────────────────────────

async def contact_us(message: types.Message):
    await message.answer(
        "📞 <b>Biz bilan bog'lanish:</b>\n\n"
        "📞 <b>+998943265755</b>",
        parse_mode="HTML"
    )


def register_profile_handlers(dp: Dispatcher):
    # Barcha 3 tildagi tugmalar
    _ORDERS_TEXTS  = ["📦 Buyurtmalarim", "📦 Мои заказы", "📦 My Orders"]
    _FAV_TEXTS     = ["❤️ Sevimlilar", "❤️ Избранное", "❤️ Favorites"]
    _PROFILE_TEXTS = ["👤 Profil", "👤 Профиль", "👤 Profile"]
    _CONTACT_TEXTS = ["☎️ Biz bilan aloqa", "☎️ Связаться с нами", "☎️ Contact Us"]

    dp.register_message_handler(show_my_orders,  lambda m: m.text in _ORDERS_TEXTS)
    dp.register_message_handler(show_favorites,  lambda m: m.text in _FAV_TEXTS)
    dp.register_message_handler(show_profile,    lambda m: m.text in _PROFILE_TEXTS)
    dp.register_message_handler(contact_us,      lambda m: m.text in _CONTACT_TEXTS)
    dp.register_callback_query_handler(show_order_detail, lambda c: c.data.startswith('myorder_'), state="*")
    dp.register_callback_query_handler(repeat_order_handler, lambda c: c.data.startswith('repeat_'), state="*")
    dp.register_callback_query_handler(myorders_back, text="myorders_back", state="*")
    # Profil tahrirlash
    dp.register_callback_query_handler(edit_name_start, text="edit_name", state="*")
    dp.register_message_handler(edit_name_done, state=ProfileStates.editing_name)
    dp.register_callback_query_handler(edit_phone_start, text="edit_phone", state="*")
    dp.register_message_handler(edit_phone_done, state=ProfileStates.editing_phone)
    dp.register_callback_query_handler(edit_address_start, text="edit_address", state="*")
    dp.register_message_handler(edit_address_done, state=ProfileStates.editing_address)
