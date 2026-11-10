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
    Koordinatlardan aniq joy nomini (shahar, tuman/mahalla, ko'cha, uy) olish.
    Hech qachon xom GPS koordinata qaytarmaydi.
    """
    from utils.helpers import resolve_human_address
    return await resolve_human_address(None, lat, lon)


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
    # Stol raqami saqlandi — endi izoh so'ralib, keyin to'lov usuli tanlanadi
    await state.update_data(address=f"Stol raqami: {text}", lat=None, lon=None,
                            phone=None)
    await _ask_for_note(message, state, lang,
                        prefix=f"✅ <b>Stol:</b> #{text}\n\n")


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
            from utils.helpers import resolve_human_address
            user_row = await get_user(user_id)
            address = await resolve_human_address(address, lat, lon)

        # ── Eng yaqin filial va 15 km yetkazib berish zonasi tekshiruvi ──
        branch_line_prefix = ""
        if lat is not None and lon is not None:
            from utils.geo_routing import find_nearest_branch, OUT_OF_ZONE_MESSAGE_UZ
            geo_res = await find_nearest_branch(lat, lon)
            nb = geo_res.get("nearest_branch") or {}
            if not geo_res.get("in_delivery_zone", True):
                await message.answer(
                    f"⚠️ <b>{OUT_OF_ZONE_MESSAGE_UZ}</b>\n\n"
                    f"🏢 Eng yaqin filial: <b>{nb.get('name', 'Darxan Burger')}</b> ({nb.get('distance_km', 0)} km)\n"
                    f"📏 Maksimal yetkazish masofasi: <b>{nb.get('max_delivery_km', 15)} km</b>",
                    parse_mode="HTML"
                )
                return
            if nb.get("name"):
                branch_line_prefix = f"🏢 <b>Sizga eng yaqin filial:</b> {nb['name']} ({nb.get('distance_km', 0)} km)\n"
                await state.update_data(
                    branch_id=nb.get("id"),
                    branch_name=nb.get("name"),
                    distance_km=nb.get("distance_km"),
                )

        await state.update_data(address=address, lat=lat, lon=lon)

        # ── Telefon saqlangan bo'lsa — so'ramas, to'g'ridan izohga ──────────
        saved_phone = user_row['phone_number'] if user_row else None
        if saved_phone:
            await state.update_data(phone=saved_phone)
            await _ask_for_note(message, state, lang,
                                prefix=f"✅ <b>Manzil:</b> {address}\n"
                                       f"{branch_line_prefix}"
                                       f"📞 <b>Telefon:</b> {saved_phone}\n\n")
        else:
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton(get_text("btn_send_phone", lang), request_contact=True))
            markup.add(KeyboardButton(get_text("btn_cancel", lang)))
            await message.answer(
                f"✅ <b>Manzil:</b> {address}\n"
                f"{branch_line_prefix}\n"
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
        from utils.helpers import resolve_human_address
        address = await resolve_human_address(data.get("address"), lat, lon)

        # O'zbekiston chegarasi tekshiruvi
        if not _is_in_uzbekistan(lat, lon):
            await message.answer(
                get_text("not_in_uzbekistan", lang),
                parse_mode="HTML"
            )
            return

        # ── Eng yaqin filial va 15 km yetkazib berish zonasi tekshiruvi ──
        from utils.geo_routing import find_nearest_branch, OUT_OF_ZONE_MESSAGE_UZ
        geo_res = await find_nearest_branch(lat, lon)
        nb = geo_res.get("nearest_branch") or {}
        if not geo_res.get("in_delivery_zone", True):
            await message.answer(
                f"⚠️ <b>{OUT_OF_ZONE_MESSAGE_UZ}</b>\n\n"
                f"🏢 Eng yaqin filial: <b>{nb.get('name', 'Darxan Burger')}</b> ({nb.get('distance_km', 0)} km)\n"
                f"📏 Maksimal yetkazish masofasi: <b>{nb.get('max_delivery_km', 15)} km</b>",
                parse_mode="HTML"
            )
            return

        branch_line_prefix = ""
        if nb.get("name"):
            branch_line_prefix = f"🏢 <b>Sizga eng yaqin filial:</b> {nb['name']} ({nb.get('distance_km', 0)} km)\n"

        user_id = message.from_user.id
        await state.update_data(
            address=address,
            lat=lat,
            lon=lon,
            branch_id=nb.get("id"),
            branch_name=nb.get("name"),
            distance_km=nb.get("distance_km"),
        )

        user_row = await get_user(user_id)
        saved_phone = user_row['phone_number'] if user_row else None

        if saved_phone:
            await state.update_data(phone=saved_phone)
            await _ask_for_note(message, state, lang,
                                prefix=f"✅ <b>Manzil:</b> {address}\n"
                                       f"{branch_line_prefix}"
                                       f"📞 <b>Telefon:</b> {saved_phone}\n\n")
        else:
            markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(KeyboardButton(get_text("btn_send_phone", lang), request_contact=True))
            markup.add(KeyboardButton(get_text("btn_cancel", lang)))
            await message.answer(
                f"✅ <b>Manzil:</b> {address}\n"
                f"{branch_line_prefix}\n"
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
    from database.crud import get_promo_code, use_promo_code
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
    promo_d = dict(promo)
    if promo_d.get('max_uses', 0) > 0 and promo_d.get('used_count', 0) >= promo_d['max_uses']:
        await message.answer(get_text("promo_expired", lang))
        return

    await use_promo_code(code, user_id=message.from_user.id)
    await state.update_data(promo_code=code, discount_percent=promo_d['discount_percent'])
    await message.answer(
        get_text("promo_applied", lang, code=code, pct=promo_d['discount_percent']),
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
        branch_id     = data.get('branch_id')
        branch_name   = data.get('branch_name')
        distance_km   = data.get('distance_km')

        if (not branch_id or not branch_name) and lat is not None and lon is not None:
            try:
                from utils.geo_routing import find_nearest_branch
                geo_res = await find_nearest_branch(float(lat), float(lon))
                nb = geo_res.get("nearest_branch") or {}
                branch_id = nb.get("id")
                branch_name = nb.get("name")
                distance_km = nb.get("distance_km")
            except Exception:
                pass

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
            
            # Narxni yaxlitlash: masalan, 12500 -> 12000, 12550 -> 13000
            remainder = delivery_fee % 1000
            if remainder <= 500:
                delivery_fee = delivery_fee - remainder
            else:
                delivery_fee = delivery_fee + (1000 - remainder)
        else:
            delivery_fee = 0

        total_amount   = after_discount + delivery_fee

        order_id = await create_order(
            user_id=user_id, total_amount=total_amount,
            address=address, payment_method=payment_method,
            latitude=lat, longitude=lon, phone_number=phone,
            note=note, delivery_type=delivery_type,
            promo_code=promo_code, discount_amount=discount_amt,
            branch_id=branch_id, branch_name=branch_name, distance_km=distance_km,
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
            location={'lat': lat, 'lon': lon}, note=note, delivery_type=delivery_type,
            payment_method=payment_method,
            promo_code=promo_code, discount_pct=discount_pct, discount_amt=discount_amt,
            branch_name=branch_name, distance_km=distance_km,
        ))

        note_text     = f"\n  📝 <i>{note}</i>" if note else ""
        discount_text = (
            get_text(
                "promo_line", lang,
                code=promo_code or "PROMO",
                pct=discount_pct,
                items_total=items_total,
                amt=discount_amt,
                after_discount=after_discount,
            )
            if discount_amt > 0 else ""
        )

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

        # ❌ 1 daqiqalik "Buyurtmani bekor qilish" tugmasi
        from utils.order_cancel import send_customer_cancel_button
        await send_customer_cancel_button(message.bot, user_id, order_id, lang)

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
