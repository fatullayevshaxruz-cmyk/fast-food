from aiogram import types, Dispatcher
import asyncio
import time as _time
from datetime import datetime
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ContentTypes
from database.crud import get_cart_items, create_order, add_order_items, clear_cart, get_user
from utils.states import OrderStates
from keyboards.main_menu import get_user_main_menu, get_admin_main_menu
from utils.helpers import notify_admins_new_order
from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END, DELIVERY_FEE, MIN_ORDER_AMOUNT


def _get_menu_for_user(user_id):
    is_admin = str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return get_admin_main_menu() if is_admin else get_user_main_menu()


def _is_working_hours() -> bool:
    now = datetime.utcnow()
    uz_hour = (now.hour + 5) % 24
    return WORKING_HOURS_START <= uz_hour < WORKING_HOURS_END


# ── O'zbekiston geografik chegaralari ────────────────────────────────
_UZ_LAT_MIN, _UZ_LAT_MAX = 37.18, 45.60
_UZ_LON_MIN, _UZ_LON_MAX = 55.99, 73.15

def _is_in_uzbekistan(lat: float, lon: float) -> bool:
    return (_UZ_LAT_MIN <= lat <= _UZ_LAT_MAX and
            _UZ_LON_MIN <= lon <= _UZ_LON_MAX)


# ── Geocoding keshi ───────────────────────────────────────────────────
_GEO_CACHE: dict = {}
_GEO_CACHE_TTL = 30 * 60  # 30 daqiqa


async def _reverse_geocode(lat: float, lon: float) -> str:
    """Koordinatlardan faqat ko'cha yoki mahalla nomini olish."""
    import aiohttp
    cache_key = f"{lat:.4f},{lon:.4f}"
    now = _time.time()
    if cache_key in _GEO_CACHE:
        val, ts = _GEO_CACHE[cache_key]
        if now - ts < _GEO_CACHE_TTL:
            return val

    url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?format=json&lat={lat}&lon={lon}"
        f"&zoom=17&addressdetails=1&accept-language=uz,ru,en"
    )
    headers = {"User-Agent": "FastFoodBot/2.0 (food delivery uzbekistan)"}
    result = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    addr = data.get("address", {})
                    for key in ["road", "pedestrian", "footway",
                                "neighbourhood", "suburb", "quarter",
                                "residential", "city_district"]:
                        val = addr.get(key)
                        if val:
                            result = val
                            break
    except Exception:
        pass

    if not result:
        result = f"({lat:.4f}, {lon:.4f})"
    _GEO_CACHE[cache_key] = (result, now)
    return result


# ── Checkout ──────────────────────────────────────────────────────────
async def start_checkout(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    items = await get_cart_items(user_id)
    if not items:
        await call.answer("Savatingiz bo'sh!", show_alert=True)
        return
    if not _is_working_hours():
        await call.answer(
            f"⏰ Kechirasiz, biz {WORKING_HOURS_START:02d}:00 dan "
            f"{WORKING_HOURS_END:02d}:00 gacha ishlaymiz.\nErtaga kutamiz! 😊",
            show_alert=True
        )
        return

    await OrderStates.waiting_for_delivery_type.set()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🍽️ Shu yerda"), KeyboardButton("🛵 Yetkazib berish"))
    markup.add(KeyboardButton("❌ Bekor qilish"))
    await call.message.answer("Ajoyib! Buyurtmani qanday usulda qabul qilasiz?", reply_markup=markup)
    await call.answer()


async def process_delivery_type(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id

    if "Shu yerda" in text:
        await state.update_data(delivery_type="eat_in")
        await OrderStates.waiting_for_table_number.set()
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(KeyboardButton("❌ Bekor qilish"))
        await message.answer("Iltimos, stol raqamini kiriting (Masalan: 5):", reply_markup=markup)

    elif "Yetkazib berish" in text:
        items = await get_cart_items(user_id)
        total = sum(i['price'] * i['quantity'] for i in items) if items else 0
        if total < MIN_ORDER_AMOUNT:
            diff = MIN_ORDER_AMOUNT - total
            await message.answer(
                f"⚠️ <b>Yetkazib berish uchun minimal summa: {MIN_ORDER_AMOUNT:,} so'm</b>\n\n"
                f"Savatda: <b>{total:,} so'm</b>\n"
                f"Yana <b>{diff:,} so'm</b> lik mahsulot qo'shing.\n\n"
                f"Yoki <b>\"🍽️ Shu yerda\"</b> ni tanlang.",
                parse_mode="HTML"
            )
            return

        await state.update_data(delivery_type="delivery")
        await OrderStates.waiting_for_location.set()
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(KeyboardButton("📍 Joylashuvni yuborish", request_location=True))
        markup.add(KeyboardButton("❌ Bekor qilish"))
        await message.answer(
            "📍 Yetkazib berish manzilini yuboring:\n"
            "<i>GPS lokatsiya yoki matn shaklida yozib yuboring</i>",
            parse_mode="HTML",
            reply_markup=markup
        )
    else:
        await message.answer("Iltimos, pastdagi tugmalardan birini tanlang.")


async def process_table_number(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer(
            "⚠️ Iltimos, faqat <b>stol raqamini</b> yozing (masalan: 5, 12).",
            parse_mode="HTML"
        )
        return
    # Shu yerda: izoh so'ralmasdan to'g'ridan buyurtmani yakunlash
    await state.update_data(address=f"Stol raqami: {text}", lat=None, lon=None,
                            phone=None, note=None, promo_code=None, discount_percent=0)
    await finish_order(message, state)


async def cancel_order(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Buyurtma bekor qilindi.", reply_markup=_get_menu_for_user(message.from_user.id))


async def process_location(message: types.Message, state: FSMContext):
    try:
        if message.text and (message.text.startswith("/") or
                             message.text in ["🍽 Menu", "🛒 Savat", "ℹ️ Biz haqimizda", "📞 Bog'lanish"]):
            await state.finish()
            await message.answer("Buyurtma jarayoni bekor qilindi.",
                                 reply_markup=_get_menu_for_user(message.from_user.id))
            return

        lat, lon, address = None, None, None

        if message.location:
            lat = message.location.latitude
            lon = message.location.longitude
        elif message.venue:
            lat = message.venue.location.latitude
            lon = message.venue.location.longitude
            address = message.venue.address or message.venue.title
        else:
            # Matn manzil
            address = message.text

        # O'zbekiston chegarasi tekshiruvi
        if lat is not None and lon is not None and not _is_in_uzbekistan(lat, lon):
            await message.answer(
                "🌍 <b>Kechirasiz!</b>\n\n"
                "Bu kafe faqat <b>O'zbekiston</b> hududida xizmat ko'rsatadi.\n"
                "Sizning joylashuvingiz O'zbekiston chegarasidan tashqarida.\n\n"
                "Agar siz O'zbekistonda bo'lsangiz, manzilni <b>matn</b> shaklida yuboring.",
                parse_mode="HTML"
            )
            return

        # ── PARALLEL: Geocoding va telefon tekshiruvini bir vaqtda bajarish ──
        user_id = message.from_user.id

        if lat is not None and lon is not None and address is None:
            # Geocodingni background da boshlash + DB dan telefon olish — bir vaqtda
            geo_task = asyncio.create_task(_reverse_geocode(lat, lon))
            user_row = await get_user(user_id)
            address = await geo_task   # Shu paytgacha user DB dan keldi
        else:
            user_row = await get_user(user_id)

        await state.update_data(address=address, lat=lat, lon=lon)

        # ── Telefon saqlangan bo'lsa — so'ramas, to'g'ridan izohga ──────────
        saved_phone = user_row['phone_number'] if user_row else None
        if saved_phone:
            await state.update_data(phone=saved_phone)
            await _ask_for_note(message, state,
                                prefix=f"✅ <b>Manzil:</b> {address}\n"
                                       f"📞 <b>Telefon:</b> {saved_phone}\n\n")
        else:
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
            markup.add(KeyboardButton("❌ Bekor qilish"))
            await message.answer(
                f"✅ <b>Manzil:</b> {address}\n\n"
                "📞 Bog'lanish uchun telefon raqamingizni yuboring:",
                parse_mode="HTML",
                reply_markup=markup
            )
            await OrderStates.waiting_for_phone.set()

    except Exception as e:
        import traceback
        traceback.print_exc()
        await message.answer(f"Xatolik yuz berdi: {e}")


async def process_phone(message: types.Message, state: FSMContext):
    try:
        phone = message.contact.phone_number if message.contact else message.text
        await state.update_data(phone=phone)
        await _ask_for_note(message, state)
    except Exception as e:
        await message.answer(f"Xatolik yuz berdi: {e}")


async def _ask_for_note(message: types.Message, state: FSMContext, prefix: str = ""):
    """Izoh so'rash — delivery uchun."""
    await OrderStates.waiting_for_note.set()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("⏭ O'tkazib yuborish"))
    markup.add(KeyboardButton("❌ Bekor qilish"))
    await message.answer(
        prefix +
        "📝 <b>Buyurtmangizga izoh yozmoqchimisiz?</b>\n\n"
        "Masalan: <i>\"sous ko'proq\", \"achchiq qilmang\"</i>\n"
        "Bo'lmasa <b>⏭ O'tkazib yuborish</b> tugmasini bosing.",
        reply_markup=markup,
        parse_mode="HTML"
    )


async def process_note(message: types.Message, state: FSMContext):
    note = None if message.text.strip() == "⏭ O'tkazib yuborish" else message.text.strip()
    await state.update_data(note=note)

    data = await state.get_data()
    # Shu yerda (eat_in) uchun promo kod so'ralmaydi
    if data.get('delivery_type') == 'eat_in':
        await state.update_data(promo_code=None, discount_percent=0)
        await finish_order(message, state)
    else:
        await _ask_for_promo(message, state)


async def _ask_for_promo(message: types.Message, state: FSMContext):
    await OrderStates.waiting_for_promo.set()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("⏭ O'tkazib yuborish"))
    markup.add(KeyboardButton("❌ Bekor qilish"))
    await message.answer(
        "🎟 <b>Promo kodingiz bormi?</b>\n\n"
        "Kodni yozing yoki <b>⏭ O'tkazib yuborish</b> tugmasini bosing.",
        reply_markup=markup,
        parse_mode="HTML"
    )


async def process_promo(message: types.Message, state: FSMContext):
    from database.crud import get_promo_code, use_promo_code, check_user_promo_used

    if message.text.strip() == "⏭ O'tkazib yuborish":
        await state.update_data(promo_code=None, discount_percent=0)
        await finish_order(message, state)
        return

    code = message.text.strip().upper()
    promo = await get_promo_code(code)
    if not promo:
        await message.answer("❌ Bunday promo kod topilmadi. Qaytadan yozing yoki o'tkazib yuboring.")
        return
    if promo['max_uses'] > 0 and promo['used_count'] >= promo['max_uses']:
        await message.answer("⚠️ Bu promo kod tugagan. Boshqa kod yozing yoki o'tkazib yuboring.")
        return
    already_used = await check_user_promo_used(message.from_user.id, code)
    if already_used:
        await message.answer("⚠️ Siz bu kodni allaqachon ishlatgansiz. O'tkazib yuboring.")
        return

    await use_promo_code(code, user_id=message.from_user.id)
    await state.update_data(promo_code=code, discount_percent=promo['discount_percent'])
    await message.answer(
        f"✅ Promo kod <b>{code}</b> qo'llandi!\n"
        f"💰 Chegirma: <b>{promo['discount_percent']}%</b>",
        parse_mode="HTML"
    )
    await finish_order(message, state)


async def finish_order(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        user_id = message.from_user.id
        phone         = data.get('phone')
        address       = data.get('address')
        lat           = data.get('lat')
        lon           = data.get('lon')
        note          = data.get('note')
        delivery_type = data.get('delivery_type', 'delivery')
        discount_pct  = data.get('discount_percent', 0)
        promo_code    = data.get('promo_code')

        items = await get_cart_items(user_id)
        if not items:
            await message.answer("Savat bo'shab qoldi!", reply_markup=_get_menu_for_user(user_id))
            await state.finish()
            return

        items_total    = sum(i['price'] * i['quantity'] for i in items)
        discount_amt   = int(items_total * discount_pct / 100) if discount_pct > 0 else 0
        after_discount = items_total - discount_amt
        delivery_fee   = DELIVERY_FEE if delivery_type == "delivery" else 0
        total_amount   = after_discount + delivery_fee

        order_id = await create_order(
            user_id=user_id, total_amount=total_amount,
            address=address, payment_method="Naqd (Yetkazib berilganda)",
            latitude=lat, longitude=lon, phone_number=phone,
            note=note, delivery_type=delivery_type
        )
        await add_order_items(order_id, items)
        await clear_cart(user_id)

        receipt = "".join(f"  ▫️ {i['name']} x {i['quantity']} = {i['price']*i['quantity']:,} so'm\n"
                          for i in items)

        await state.finish()

        # Kanalga xabar — background da (foydalanuvchini kutdirmaydi)
        asyncio.create_task(notify_admins_new_order(
            bot=message.bot, order_id=order_id, total_amount=total_amount,
            user=message.from_user, items=items, phone=phone, address=address,
            location={'lat': lat, 'lon': lon}, note=note, delivery_type=delivery_type
        ))

        note_text     = f"\n  📝 <i>{note}</i>" if note else ""
        discount_text = (f"\n  🎟 Promo ({promo_code}): <b>-{discount_amt:,} so'm</b>"
                         if discount_amt > 0 else "")

        if delivery_type == "eat_in":
            success_text = (
                f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
                f"📋 <b>Buyurtma #{order_id}</b>\n"
                f"🍽️ <b>Shu yerda</b> | {address}\n\n"
                f"{receipt}"
                f"{discount_text}\n"
                f"  💰 <b>Jami: {after_discount:,} so'm</b>"
                f"{note_text}\n\n"
                f"🍖 Ofitsiant olib keladi. Yoqimli ishtaha! 😋"
            )
        else:
            success_text = (
                f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
                f"📋 <b>Buyurtma #{order_id}</b>\n"
                f"🛵 <b>Yetkazib berish</b>\n\n"
                f"{receipt}"
                f"{discount_text}\n"
                f"  🛵 Yetkazish: <b>{delivery_fee:,} so'm</b>\n"
                f"  ━━━━━━━━━━━━━━━\n"
                f"  💰 <b>Jami: {total_amount:,} so'm</b>"
                f"{note_text}\n\n"
                f"🛵 Yetkazib beruvchi siz bilan bog'lanadi.\n"
                f"<i>(To'lovni mahsulotni qabul qilganda to'laysiz)</i>\n\n"
                f"Rahmat! Yoqimli ishtaha! 😋"
            )

        await message.answer(success_text, reply_markup=_get_menu_for_user(user_id), parse_mode="HTML")

    except Exception as e:
        import traceback
        traceback.print_exc()
        await message.answer(f"Buyurtmani yakunlashda xatolik: {e}")


def register_order_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(start_checkout, text="checkout")
    dp.register_message_handler(cancel_order, text="❌ Bekor qilish", state="*")
    dp.register_message_handler(process_delivery_type, state=OrderStates.waiting_for_delivery_type)
    dp.register_message_handler(process_table_number, state=OrderStates.waiting_for_table_number)
    dp.register_message_handler(process_location,
                                content_types=['location', 'venue', 'text'],
                                state=OrderStates.waiting_for_location)
    dp.register_message_handler(process_phone,
                                content_types=['contact', 'text'],
                                state=OrderStates.waiting_for_phone)
    dp.register_message_handler(process_note, state=OrderStates.waiting_for_note)
    dp.register_message_handler(process_promo, state=OrderStates.waiting_for_promo)
