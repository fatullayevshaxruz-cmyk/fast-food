from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.crud import (
    get_user_orders, get_order_items_detail, get_order_by_id, get_user,
    get_favorites, repeat_order_to_cart, update_user_name, update_user_phone,
    update_user_address, get_user_language
)
from keyboards.admin_keyboard import STATUS_LABELS
from utils.states import ProfileStates
from utils.i18n import get_text


# ── Buyurtmalarim ────────────────────────────────────────────────────

async def show_my_orders(message: types.Message, user_id: int = None):
    if user_id is None:
        user_id = message.from_user.id
    lang = await get_user_language(user_id)
    orders = await get_user_orders(user_id)

    if not orders:
        await message.answer(get_text("no_orders_yet", lang))
        return

    text = get_text("orders_title", lang)
    markup = InlineKeyboardMarkup(row_width=1)

    for order in orders:
        status = order['status'] or 'pending'
        status_text = STATUS_LABELS.get(status, f"⏳ {status}")
        created = order['created_at']
        date_str = (
            created.strftime('%Y-%m-%d %H:%M')
            if hasattr(created, 'strftime')
            else str(created)[:16] if created else "—"
        )
        text += get_text("order_row", lang,
                         id=order['id'],
                         status=status_text,
                         amount=order['total_amount'],
                         date=date_str)
        markup.add(InlineKeyboardButton(
            get_text("btn_order_detail", lang, id=order['id']),
            callback_data=f"myorder_{order['id']}"
        ))

    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def show_order_detail(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    order_id = int(call.data.split("_")[1])
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer(get_text("order_not_found", lang), show_alert=True)
        return

    items = await get_order_items_detail(order_id)
    status = order['status'] or 'pending'
    status_text = STATUS_LABELS.get(status, f"⏳ {status}")
    created = order['created_at']
    date_str = (
        created.strftime('%Y-%m-%d %H:%M')
        if hasattr(created, 'strftime')
        else str(created)[:16] if created else "—"
    )

    text = get_text("order_detail_title", lang, id=order['id'])
    text += get_text("order_detail_body", lang,
                     date=date_str,
                     status=status_text,
                     address=order['delivery_address'] or '—',
                     phone=order['phone_number'] or '—')

    note = None
    try:
        note = order['note']
    except (KeyError, IndexError):
        pass
    if note:
        text += f"📝 <i>{note}</i>\n"

    text += get_text("order_items_title", lang)
    total = 0
    for item in items:
        item_total = item['price_at_time'] * item['quantity']
        total += item_total
        if lang == "ru":
            text += f"  ▫️ {item['name']} x {item['quantity']} = {item_total:,} сум\n"
        elif lang == "en":
            text += f"  ▫️ {item['name']} x {item['quantity']} = {item_total:,} sum\n"
        else:
            text += f"  ▫️ {item['name']} x {item['quantity']} = {item_total:,} so'm\n"

    text += get_text("order_total", lang, total=total)

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(get_text("btn_repeat_order", lang), callback_data=f"repeat_{order_id}"),
        InlineKeyboardButton(get_text("btn_back", lang), callback_data="myorders_back")
    )

    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await call.answer()


async def repeat_order_handler(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    order_id = int(call.data.split("_")[1])
    count = await repeat_order_to_cart(call.from_user.id, order_id)
    if count > 0:
        await call.answer(get_text("repeat_success", lang, count=count), show_alert=True)
    else:
        await call.answer(get_text("no_items_in_order", lang), show_alert=True)


async def myorders_back(call: types.CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    await show_my_orders(call.message, user_id=call.from_user.id)
    await call.answer()


# ── Sevimlilar ───────────────────────────────────────────────────────

async def show_favorites(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    user_id = message.from_user.id
    favs = await get_favorites(user_id)
    if not favs:
        await message.answer(get_text("no_favorites", lang))
        return

    text = get_text("favorites_title", lang)
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
    lang = await get_user_language(message.from_user.id)
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer(get_text("profile_not_found", lang))
        return

    name = user['full_name'] or '—'
    phone = user['phone_number'] or '—'
    address = None
    try:
        address = user['default_address']
    except (KeyError, IndexError):
        pass
    address = address or '—'

    text = get_text("profile_title", lang, name=name, phone=phone, address=address)

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(get_text("btn_edit_name", lang), callback_data="edit_name"),
        InlineKeyboardButton(get_text("btn_edit_phone", lang), callback_data="edit_phone"),
        InlineKeyboardButton(get_text("btn_edit_address", lang), callback_data="edit_address"),
    )
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def edit_name_start(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    await ProfileStates.editing_name.set()
    await call.message.answer(get_text("ask_new_name", lang))
    await call.answer()


async def edit_name_done(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    name = message.text.strip()
    if len(name) < 2:
        await message.answer(get_text("name_too_short", lang))
        return
    await update_user_name(message.from_user.id, name)
    await state.finish()
    await message.answer(get_text("name_updated", lang, name=name), parse_mode="HTML")


async def edit_phone_start(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    await ProfileStates.editing_phone.set()
    await call.message.answer(get_text("ask_new_phone", lang))
    await call.answer()


async def edit_phone_done(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    phone = message.text.strip()
    await update_user_phone(message.from_user.id, phone)
    await state.finish()
    await message.answer(get_text("phone_updated", lang, phone=phone), parse_mode="HTML")


async def edit_address_start(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    await ProfileStates.editing_address.set()
    await call.message.answer(get_text("ask_new_address", lang))
    await call.answer()


async def edit_address_done(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    address = message.text.strip()
    await update_user_address(message.from_user.id, address)
    await state.finish()
    await message.answer(get_text("address_updated", lang, address=address), parse_mode="HTML")


# ── Aloqa ────────────────────────────────────────────────────────────

async def contact_us(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    await message.answer(get_text("contact_text", lang), parse_mode="HTML")


def register_profile_handlers(dp: Dispatcher):
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
    dp.register_callback_query_handler(edit_name_start, text="edit_name", state="*")
    dp.register_message_handler(edit_name_done, state=ProfileStates.editing_name)
    dp.register_callback_query_handler(edit_phone_start, text="edit_phone", state="*")
    dp.register_message_handler(edit_phone_done, state=ProfileStates.editing_phone)
    dp.register_callback_query_handler(edit_address_start, text="edit_address", state="*")
    dp.register_message_handler(edit_address_done, state=ProfileStates.editing_address)
