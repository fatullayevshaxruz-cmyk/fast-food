from aiogram import types, Dispatcher
import asyncio
import time as _time
from datetime import datetime
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ContentTypes, WebAppInfo
from database.crud import get_cart_items, create_order, add_order_items, clear_cart, get_user, get_user_language, get_product_name
from utils.states import OrderStates
from keyboards.main_menu import get_user_main_menu, get_admin_main_menu
from utils.helpers import notify_admins_new_order
from utils.i18n import get_text
from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END, DELIVERY_FEE, MIN_ORDER_AMOUNT
import os
# To'lov handler — aylanma importdan qochish uchun ichida import qilinadi

# ── WebApp URL ─────────────────────────────────────────────────────────
# Render deployment URL — .env dan olinadi, fallback bilan
_RENDER_URL = os.getenv("RENDER_URL", "https://fast-food-1-p4bx.onrender.com")
MAP_WEBAPP_URL = f"{_RENDER_URL}/webapp/map.html"


def _get_menu_for_user(user_id, lang="uz"):
    is_admin = str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return get_admin_main_menu(lang) if is_admin else get_user_main_menu(lang)


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

# Shahar/mamlakat darajasidagi so'zlar — bularni manzil sifatida ko'rsatmaymiz
_SKIP_WORDS = {
    "toshkent", "samarqand", "buxoro", "namangan", "andijon",
    "farg'ona", "nukus", "qarshi", "termiz", "jizzax", "navoiy",
    "o'zbekiston", "uzbekistan", "uzbekiston", "republic", "viloyat",
    "tuman", "district", "region", "city", "shahar"
}


async def _reverse_geocode(lat: float, lon: float) -> str:
    """
    Koordinatlardan faqat ko'cha yoki mahalla nomini olish.
    O'zbekiston uchun optimallashtirilgan Nominatim parser.
    """
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
        f"&zoom=17&addressdetails=1&accept-language=uz,ru"
    )
    headers = {"User-Agent": "FastFoodBot/2.0 (food delivery uzbekistan)"}
    result = None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    addr = data.get("address", {})

                    # 1️⃣ address dict dan aniq maydonlar (ustunlik tartibi)
                    for key in [
                        "road", "pedestrian", "footway", "path",
                        "neighbourhood", "quarter", "residential",
                        "suburb", "hamlet", "village", "city_district"
                    ]:
                        val = addr.get(key, "").strip()
                        if val and val.lower() not in _SKIP_WORDS:
                            result = val
                            break

                    # 2️⃣ Agar topilmasa — display_name dan aqlli parsing
                    if not result:
                        display = data.get("display_name", "")
                        parts = [p.strip() for p in display.split(",")]
                        for part in parts:
                            if (not part
                                    or part.isdigit()
                                    or any(skip in part.lower() for skip in _SKIP_WORDS)):
                                continue
                            result = part
                            break

                    # 3️⃣ Nominatim top-level "name" maydoni (do'kon, bino nomi)
                    if not result:
                        top_name = data.get("name", "").strip()
                        if top_name and top_name.lower() not in _SKIP_WORDS:
                            result = top_name

    except Exception:
        pass

    if not result:
        result = f"({lat:.4f}, {lon:.4f})"

    _GEO_CACHE[cache_key] = (result, now)
    return result


# ── Checkout ──────────────────────────────────────────────────────────
async def start_checkout(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    lang = await get_user_language(user_id)
    items = await get_cart_items(user_id)
    if not items:
        await call.answer(get_text("cart_empty", lang), show_alert=True)
        return
    if not _is_working_hours():
        await call.answer(
            get_text("not_working_hours", lang,
                     start=WORKING_HOURS_START,
                     end=WORKING_HOURS_END),
            show_alert=True
        )
        return

    await OrderStates.waiting_for_delivery_type.set()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton(get_text("btn_eat_in", lang)),
        KeyboardButton(get_text("btn_delivery", lang))
    )
    markup.add(KeyboardButton(get_text("btn_cancel", lang)))
    await call.message.answer(
        get_text("choose_delivery_type", lang),
        reply_markup=markup
    )
    await call.answer()


async def process_delivery_type(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = message.from_user.id
    lang = await get_user_language(user_id)

    eat_in_texts = [get_text("btn_eat_in", l) for l in ("uz", "ru", "en")]
    delivery_texts = [get_text("btn_delivery", l) for l in ("uz", "ru", "en")]

    if text in eat_in_texts:
        await state.update_data(delivery_type="eat_in")
        await OrderStates.waiting_for_table_number.set()
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(KeyboardButton(get_text("btn_cancel", lang)))
        await message.answer(
            get_text("ask_table_number", lang),
            reply_markup=markup
        )

    elif text in delivery_texts:
        items = await get_cart_items(user_id)
        total = sum(i['price'] * i['quantity'] for i in items) if items else 0
        if total < MIN_ORDER_AMOUNT:
            diff = MIN_ORDER_AMOUNT - total
            await message.answer(
                get_text("min_order_warning", lang,
                         min=MIN_ORDER_AMOUNT,
                         total=total,
                         diff=diff),
                parse_mode="HTML"
            )
            return

        await state.update_data(delivery_type="delivery")
        await OrderStates.waiting_for_location.set()

        # ── "Xaritadan aniqlash" tugmasi — WebApp bilan ──────────
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(
            KeyboardButton(
                get_text("btn_send_location", lang),
                request_location=True
            )
        )
        # WebApp URL ga til parametrini qo'shamiz
        map_url = f"{MAP_WEBAPP_URL}?lang={lang}"
        markup.add(
            KeyboardButton(
                get_text("btn_map_location", lang),
                web_app=WebAppInfo(url=map_url)
            )
        )
        markup.add(KeyboardButton(get_text("btn_cancel", lang)))

        await message.answer(
            get_text("ask_location", lang),
            parse_mode="HTML",
            reply_markup=markup
        )
    else:
        await message.answer(get_text("select_incorrect", lang))


async def process_table_number(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer(
            get_text("invalid_table_number", lang),
            parse_mode="HTML"
        )
        return
    # Shu yerda: izoh so'ralmasdan to'g'ridan buyurtmani yakunlash
    await state.update_data(address=f"Stol raqami: {text}", lat=None, lon=None,
                            phone=None, note=None, promo_code=None, discount_percent=0)
    await finish_order(message, state)


async def cancel_order(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    await state.finish()
    await message.answer(
        get_text("order_cancelled", lang),
        reply_markup=_get_menu_for_user(message.from_user.id, lang)
    )


async def process_location(message: types.Message, state: FSMContext):
    """GPS yoki matn manzilni qayta ishlash."""
    try:
        lang = await get_user_language(message.from_user.id)

        if message.text and (message.text.startswith("/") or
                             message.text in [
                                 get_text("btn_menu", "uz"), get_text("btn_menu", "ru"), get_text("btn_menu", "en"),
                                 get_text("btn_cart", "uz"), get_text("btn_cart", "ru"), get_text("btn_cart", "en"),
                             ]):
            await state.finish()
            await message.answer(
                get_text("location_cancelled", lang),
                reply_markup=_get_menu_for_user(message.from_user.id, lang)
            )
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
                get_text("not_in_uzbekistan", lang),
                parse_mode="HTML"
            )
            return

        # ── PARALLEL: Geocoding va telefon tekshiruvini bir vaqtda bajarish ──
        user_id = message.from_user.id

        if lat is not None and lon is not None and address is None:
            geo_task = asyncio.create_task(_reverse_geocode(lat, lon))
            user_row = await get_user(user_id)
            address = await geo_task
        else:
            user_row = await get_user(user_id)

        await state.update_data(address=address, lat=lat, lon=lon)

        # ── Telefon saqlangan bo'lsa — so'ramas, to'g'ridan izohga ──────────
        saved_phone = user_row['phone_number'] if user_row else None
        if saved_phone:
            await state.update_data(phone=saved_phone)
            await _ask_for_note(message, state, lang,
                                prefix=f"✅ <b>Manzil:</b> {address}\n"
                                       f"📞 <b>Telefon:</b> {saved_phone}\n\n")
        else:
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton(get_text("btn_send_phone", lang), request_contact=True))
            markup.add(KeyboardButton(get_text("btn_cancel", lang)))
            await message.answer(
                f"✅ <b>Manzil:</b> {address}\n\n"
                + get_text("ask_phone", lang),
                parse_mode="HTML",
                reply_markup=markup
            )
            await OrderStates.waiting_for_phone.set()

    except Exception as e:
        import traceback
        traceback.print_exc()
        await message.answer(f"Xatolik yuz berdi: {e}")


async def process_webapp_location(message: types.Message, state: FSMContext):
    """Telegram WebApp xaritasidan kelgan joylashuv ma'lumotini qayta ishlash."""
    import json
    try:
        lang = await get_user_language(message.from_user.id)
        data_str = message.web_app_data.data
        data = json.loads(data_str)

        lat = float(data["lat"])
        lon = float(data["lon"])
        address = data.get("address", f"({lat:.4f}, {lon:.4f})")

        # O'zbekiston chegarasi tekshiruvi
        if not _is_in_uzbekistan(lat, lon):
            await message.answer(
                get_text("not_in_uzbekistan", lang),
                parse_mode="HTML"
            )
            return

        user_id = message.from_user.id
        await state.update_data(address=address, lat=lat, lon=lon)

        user_row = await get_user(user_id)
        saved_phone = user_row['phone_number'] if user_row else None

        if saved_phone:
            await state.update_data(phone=saved_phone)
            await _ask_for_note(message, state, lang,
                                prefix=f"✅ <b>Manzil:</b> {address}\n"
                                       f"📞 <b>Telefon:</b> {saved_phone}\n\n")
        else:
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton(get_text("btn_send_phone", lang), request_contact=True))
            markup.add(KeyboardButton(get_text("btn_cancel", lang)))
            await message.answer(
                f"✅ <b>Manzil:</b> {address}\n\n"
                + get_text("ask_phone", lang),
                parse_mode="HTML",
                reply_markup=markup
            )
            await OrderStates.waiting_for_phone.set()

    except Exception as e:
        import traceback
        traceback.print_exc()
        await message.answer(f"Xarita xatoligi: {e}")


async def process_phone(message: types.Message, state: FSMContext):
    try:
        lang = await get_user_language(message.from_user.id)
        phone = message.contact.phone_number if message.contact else message.text
        await state.update_data(phone=phone)
        await _ask_for_note(message, state, lang)
    except Exception as e:
        await message.answer(f"Xatolik yuz berdi: {e}")


async def _ask_for_note(message: types.Message, state: FSMContext,
                        lang: str = "uz", prefix: str = ""):
    """Izoh so'rash — delivery uchun."""
    await OrderStates.waiting_for_note.set()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton(get_text("btn_skip", lang)))
    markup.add(KeyboardButton(get_text("btn_cancel", lang)))
    await message.answer(
        prefix + get_text("ask_note", lang),
        reply_markup=markup,
        parse_mode="HTML"
    )


async def process_note(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    skip_texts = [get_text("btn_skip", l) for l in ("uz", "ru", "en")]
    note = None if message.text.strip() in skip_texts else message.text.strip()
    await state.update_data(note=note)

    data = await state.get_data()
    if data.get('delivery_type') == 'eat_in':
        await state.update_data(promo_code=None, discount_percent=0)
        from handlers.payment import ask_payment_method
        await ask_payment_method(message, state)
    else:
        await _ask_for_promo(message, state, lang)


async def _ask_for_promo(message: types.Message, state: FSMContext, lang: str = "uz"):
    await OrderStates.waiting_for_promo.set()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton(get_text("btn_skip", lang)))
    markup.add(KeyboardButton(get_text("btn_cancel", lang)))
    await message.answer(
        get_text("ask_promo", lang),
        reply_markup=markup,
        parse_mode="HTML"
    )


async def process_promo(message: types.Message, state: FSMContext):
    from database.crud import get_promo_code, use_promo_code, check_user_promo_used
    from handlers.payment import ask_payment_method

    lang = await get_user_language(message.from_user.id)
    skip_texts = [get_text("btn_skip", l) for l in ("uz", "ru", "en")]

    if message.text.strip() in skip_texts:
        await state.update_data(promo_code=None, discount_percent=0)
        await ask_payment_method(message, state)
        return

    code = message.text.strip().upper()
    promo = await get_promo_code(code)
    if not promo:
        await message.answer(get_text("promo_not_found", lang))
        return
    if promo['max_uses'] > 0 and promo['used_count'] >= promo['max_uses']:
        await message.answer(get_text("promo_expired", lang))
        return
    already_used = await check_user_promo_used(message.from_user.id, code)
    if already_used:
        await message.answer(get_text("promo_already_used", lang))
        return

    await use_promo_code(code, user_id=message.from_user.id)
    await state.update_data(promo_code=code, discount_percent=promo['discount_percent'])
    await message.answer(
        get_text("promo_applied", lang, code=code, pct=promo['discount_percent']),
        parse_mode="HTML"
    )
    await ask_payment_method(message, state)


async def finish_order(message: types.Message, state: FSMContext,
                       payment_method: str = "Naqd (Yetkazib berilganda)"):
    try:
        data = await state.get_data()
        user_id = message.from_user.id
        lang = await get_user_language(user_id)
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
            await message.answer(
                get_text("cart_empty", lang),
                reply_markup=_get_menu_for_user(user_id, lang)
            )
            await state.finish()
            return

        items_total    = sum(i['price'] * i['quantity'] for i in items)
        discount_amt   = int(items_total * discount_pct / 100) if discount_pct > 0 else 0
        after_discount = items_total - discount_amt

        # ── Masofaga qarab yetkazish narxi ─────────────────────────
        if delivery_type == "delivery":
            if lat is not None and lon is not None:
                try:
                    from utils.delivery_fee import calculate_delivery_fee
                    from config import (RESTAURANT_LAT, RESTAURANT_LON, DELIVERY_BASE_FEE,
                                       DELIVERY_EXTRA_PER_KM, DELIVERY_FREE_KM)
                    delivery_fee, _dist_km = await calculate_delivery_fee(
                        float(lat), float(lon),
                        RESTAURANT_LAT, RESTAURANT_LON,
                        DELIVERY_BASE_FEE, DELIVERY_EXTRA_PER_KM,
                        DELIVERY_FREE_KM, DELIVERY_FEE,
                    )
                except Exception:
                    delivery_fee = DELIVERY_FEE
            else:
                delivery_fee = DELIVERY_FEE
        else:
            delivery_fee = 0

        total_amount   = after_discount + delivery_fee

        order_id = await create_order(
            user_id=user_id, total_amount=total_amount,
            address=address, payment_method=payment_method,
            latitude=lat, longitude=lon, phone_number=phone,
            note=note, delivery_type=delivery_type
        )
        await add_order_items(order_id, items)
        await clear_cart(user_id)

        # Chek (til bo'yicha)
        receipt = "".join(
            get_text("item_line", lang, name=get_product_name(i, lang), qty=i['quantity'],
                     total=i['price'] * i['quantity']) + "\n"
            for i in items
        )

        await state.finish()

        # Kanalga xabar — background da
        asyncio.create_task(notify_admins_new_order(
            bot=message.bot, order_id=order_id, total_amount=total_amount,
            user=message.from_user, items=items, phone=phone, address=address,
            location={'lat': lat, 'lon': lon}, note=note, delivery_type=delivery_type
        ))

        note_text     = f"\n  📝 <i>{note}</i>" if note else ""
        discount_text = (get_text("promo_line", lang, code=promo_code, amt=discount_amt)
                         if discount_amt > 0 else "")

        if delivery_type == "eat_in":
            success_text = get_text("order_success_eat_in", lang,
                                    order_id=order_id,
                                    address=address,
                                    receipt=receipt,
                                    discount=discount_text,
                                    total=after_discount,
                                    note=note_text)
        else:
            success_text = get_text("order_success_delivery", lang,
                                    order_id=order_id,
                                    receipt=receipt,
                                    discount=discount_text,
                                    delivery_fee=delivery_fee,
                                    total=total_amount,
                                    note=note_text)

        await message.answer(
            success_text,
            reply_markup=_get_menu_for_user(user_id, lang),
            parse_mode="HTML"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        await message.answer(f"Buyurtmani yakunlashda xatolik: {e}")


def register_order_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(start_checkout, text="checkout")
    dp.register_message_handler(cancel_order, text="❌ Bekor qilish", state="*")
    dp.register_message_handler(cancel_order, text="❌ Отмена", state="*")
    dp.register_message_handler(cancel_order, text="❌ Cancel", state="*")
    dp.register_message_handler(process_delivery_type,
                                state=OrderStates.waiting_for_delivery_type)
    dp.register_message_handler(process_table_number,
                                state=OrderStates.waiting_for_table_number)
    # WebApp ma'lumotlari — waiting_for_location holatida
    dp.register_message_handler(process_webapp_location,
                                content_types=ContentTypes.WEB_APP_DATA,
                                state=OrderStates.waiting_for_location)
    dp.register_message_handler(process_location,
                                content_types=['location', 'venue', 'text'],
                                state=OrderStates.waiting_for_location)
    dp.register_message_handler(process_phone,
                                content_types=['contact', 'text'],
                                state=OrderStates.waiting_for_phone)
    dp.register_message_handler(process_note, state=OrderStates.waiting_for_note)
    dp.register_message_handler(process_promo, state=OrderStates.waiting_for_promo)
