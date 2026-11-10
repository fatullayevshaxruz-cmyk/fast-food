"""
handlers/webapp_menu.py
========================
Telegram WebApp interaktiv menyusidan kelgan to'liq buyurtma ma'lumotlarini qayta ishlash.

Oqim:
  1. Foydalanuvchi webapp/app.html da taom tanlab, yetkazib berish turini
     va manzilni to'ldirib "Buyurtma berish" bosadi
  2. Telegram.WebApp.sendData(JSON) → bot WEB_APP_DATA xabari oladi
  3. Bu handler JSON ni parse qilib, to'liq order yaratadi,
     adminlarga/kanalga xabar jo'natadi, mijozga tasdiqlama yuboradi
"""

import json
import asyncio
import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import ContentTypes

from database.crud import (
    clear_cart, add_to_cart, get_cart_items, create_order,
    add_order_items, get_user_language, get_user, use_promo_code,
    get_promo_code, check_user_promo_used, get_product_name
)
from utils.helpers import notify_admins_new_order
from utils.i18n import get_text
from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END, DELIVERY_FEE, MIN_ORDER_AMOUNT
from security.rate_limiter import check_and_record_order_idempotency
from security.sanitization import (
    sanitize_text,
    clamp_quantity,
    validate_coordinates,
    MAX_CART_DISTINCT_ITEMS,
)

log = logging.getLogger(__name__)


def _is_admin(user_id):
    return str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]


def _is_working_hours() -> bool:
    from datetime import datetime
    now = datetime.utcnow()
    uz_hour = (now.hour + 5) % 24
    return WORKING_HOURS_START <= uz_hour < WORKING_HOURS_END


def _get_menu_for_user(user_id, lang="uz"):
    from keyboards.main_menu import get_admin_main_menu, get_user_main_menu
    return get_admin_main_menu(lang) if _is_admin(user_id) else get_user_main_menu(lang)


def _is_webapp_cart(message: types.Message) -> bool:
    """WebApp dan kelgan savat/buyurtma xabarini aniqlash."""
    try:
        if not message.web_app_data:
            return False
        data = json.loads(message.web_app_data.data)
        return data.get("type") == "webapp_cart"
    except Exception:
        return False


async def process_webapp_cart(message: types.Message, state: FSMContext):
    """
    WebApp dan kelgan to'liq buyurtmani qayta ishlash:
      1. Savatni tozalash va mahsulotlarni qo'shish
      2. Delivery fee hisoblash
      3. Order yaratish (DB)
      4. Admin/kanal ga xabar yuborish
      5. Mijozga tasdiqlama xabar
    """
    try:
        user_id = message.from_user.id
        lang = await get_user_language(user_id)

        # Ish vaqtini tekshirish
        if not _is_working_hours():
            await message.answer(
                get_text("not_working_hours", lang,
                         start=WORKING_HOURS_START, end=WORKING_HOURS_END),
                parse_mode="HTML"
            )
            return

        raw = message.web_app_data.data
        data = json.loads(raw)
        items_raw = data.get("items", [])

        if not items_raw or not isinstance(items_raw, list):
            await message.answer(get_text("webapp_cart_empty", lang))
            return

        delivery_type  = sanitize_text(data.get("delivery_type", "delivery"), max_len=20)
        if delivery_type not in ("delivery", "eat_in"):
            delivery_type = "delivery"
        address        = sanitize_text(data.get("address", ""), max_len=250)
        payment_method = sanitize_text(data.get("payment_method", "Naqd (Yetkazib berilganda)"), max_len=80)
        promo_code     = sanitize_text(data.get("promo_code") or "", max_len=30) or None
        lat, lon       = validate_coordinates(data.get("lat"), data.get("lon"))

        if delivery_type == "delivery":
            from utils.helpers import resolve_human_address
            address = await resolve_human_address(address, lat, lon)

        # ── 0-A. Sozlanmagan online to'lov tizimini rad etish ─────────
        from utils.payment_links import is_payment_method_available
        if not is_payment_method_available(payment_method):
            await message.answer(
                "⚠️ Tanlangan online to'lov usuli vaqtincha mavjud emas. "
                "Iltimos, naqd to'lovni tanlab qayta buyurtma bering."
            )
            return

        # ── 0. Dublikat buyurtma (Replay / Flood) himoyasi ────────────
        if not check_and_record_order_idempotency(user_id, items_raw, delivery_type, address):
            return

        # ── 1. Savatni tozalash va yangi mahsulotlarni qo'shish ──────
        await clear_cart(user_id)
        added = 0
        for item in items_raw[:MAX_CART_DISTINCT_ITEMS]:
            pid = item.get("product_id")
            qty = clamp_quantity(item.get("quantity", 1))
            if pid and qty > 0:
                await add_to_cart(user_id, int(pid), qty)
                added += qty

        if added == 0:
            await message.answer(get_text("webapp_cart_empty", lang))
            return

        # ── 2. Savat ma'lumotlarini olish ────────────────────────────
        raw_items = await get_cart_items(user_id)
        if not raw_items:
            await message.answer(get_text("webapp_cart_empty", lang))
            return
        items = [dict(i) for i in raw_items]

        # Yetkazib berish turi belgisi
        if delivery_type == "eat_in":
            delivery_label = "Shu yerda"
        else:
            delivery_label = "Yetkazib berish"

        # ── 3. Promo kod tekshirish ───────────────────────────────────
        discount_pct = 0
        if promo_code:
            promo_code = promo_code.strip().upper()
            try:
                already_used = await check_user_promo_used(user_id, promo_code)
                promo = await get_promo_code(promo_code)
                if promo and not already_used:
                    promo_d = dict(promo)
                    if promo_d.get("max_uses", 0) == 0 or promo_d.get("used_count", 0) < promo_d["max_uses"]:
                        discount_pct = promo_d.get("discount_percent", 0)
                        await use_promo_code(promo_code, user_id=user_id)
            except Exception as e:
                log.warning(f"Promo kod xatosi: {e}")

        # ── 4. Narxlarni hisoblash ────────────────────────────────────
        items_total   = sum(i['price'] * i['quantity'] for i in items)
        discount_amt  = int(items_total * discount_pct / 100) if discount_pct > 0 else 0
        after_discount = items_total - discount_amt

        if delivery_type == "delivery":
            # Masofaga qarab narx (koordinat bo'lsa)
            delivery_fee_val = DELIVERY_FEE
            if lat is not None and lon is not None:
                try:
                    from utils.delivery_fee import calculate_delivery_fee
                    from config import (RESTAURANT_LAT, RESTAURANT_LON,
                                       DELIVERY_BASE_FEE, DELIVERY_EXTRA_PER_KM,
                                       DELIVERY_FREE_KM)
                    delivery_fee_val, _ = await calculate_delivery_fee(
                        float(lat), float(lon),
                        RESTAURANT_LAT, RESTAURANT_LON,
                        DELIVERY_BASE_FEE, DELIVERY_EXTRA_PER_KM,
                        DELIVERY_FREE_KM, DELIVERY_FEE,
                    )
                except Exception:
                    pass

            # Yaxlitlash: 12500 → 12000, 12550 → 13000
            remainder = delivery_fee_val % 1000
            if remainder <= 500:
                delivery_fee_val -= remainder
            else:
                delivery_fee_val += (1000 - remainder)
        else:
            delivery_fee_val = 0

        total_amount = after_discount + delivery_fee_val

        # ── 5. Foydalanuvchi telefon raqami ──────────────────────────
        user_row = await get_user(user_id)
        phone = user_row['phone_number'] if user_row else None

        pay_low = str(payment_method or '').lower()
        is_click = "click" in pay_low
        is_payme = "payme" in pay_low
        is_online = is_click or is_payme or ("online" in pay_low)

        nearest_branch = None
        branch_id = None
        branch_name = None
        distance_km = None
        if lat is not None and lon is not None:
            try:
                from utils.geo_routing import find_nearest_branch
                geo_res = await find_nearest_branch(float(lat), float(lon))
                nearest_branch = geo_res.get("nearest_branch")
                if nearest_branch:
                    branch_id = nearest_branch.get("id")
                    branch_name = nearest_branch.get("name")
                    distance_km = nearest_branch.get("distance_km")
            except Exception:
                pass

        # ── 6. Buyurtmani DB ga saqlash ───────────────────────────────
        order_id = await create_order(
            user_id=user_id,
            total_amount=total_amount,
            address=address or "Manzil kiritilmagan",
            payment_method=payment_method,
            latitude=lat,
            longitude=lon,
            phone_number=phone,
            note=None,
            delivery_type=delivery_type,
            payment_status="unpaid" if is_online else "paid",
            promo_code=promo_code if discount_amt > 0 else None,
            discount_amount=discount_amt,
            branch_id=branch_id,
            branch_name=branch_name,
            distance_km=distance_km,
        )
        await add_order_items(order_id, items)
        await clear_cart(user_id)

        # ── 7. FSM ni yakunlash ───────────────────────────────────────
        await state.finish()

        # ── 8. Filial kanaliga yo'naltirish (Faqat Naqd uchun!) ────────
        # Online to'lovda toki to'lov tasdiqlanmaguncha filial kanaliga yuborilmaydi
        if not is_online:
            asyncio.create_task(notify_admins_new_order(
                bot=message.bot,
                order_id=order_id,
                total_amount=total_amount,
                user=message.from_user,
                items=items,
                phone=phone,
                address=address,
                location={'lat': lat, 'lon': lon},
                note=None,
                delivery_type=delivery_type,
                payment_method=payment_method,
                promo_code=promo_code if discount_amt > 0 else None,
                discount_pct=discount_pct,
                discount_amt=discount_amt,
                branch_name=branch_name,
                distance_km=distance_km,
            ))

        # ── 9. Mijozga chek ───────────────────────────────────────────
        receipt = "".join(
            get_text("item_line", lang, name=get_product_name(i, lang), qty=i['quantity'],
                     total=i['price'] * i['quantity']) + "\n"
            for i in items
        )

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
                                    note="")
        else:
            success_text = get_text("order_success_delivery", lang,
                                    order_id=order_id,
                                    receipt=receipt,
                                    discount=discount_text,
                                    delivery_fee=delivery_fee_val,
                                    total=total_amount,
                                    note="")

        if is_online:
            from utils.payment_links import build_pay_keyboard
            pay_kb = build_pay_keyboard(order_id, total_amount, prefer="click" if is_click else None)
            pay_prompt = "\n\n⏳ <b>DIQQAT:</b> Buyurtmangiz oshxonaga qabul qilinishi uchun to'lovni bajaring:"
            pay_msg = await message.answer(success_text + pay_prompt, reply_markup=pay_kb, parse_mode="HTML")
            await message.answer("🍔 Asosiy menyu:", reply_markup=_get_menu_for_user(user_id, lang))
            related_ids = [pay_msg.message_id]
        else:
            await message.answer(
                success_text,
                reply_markup=_get_menu_for_user(user_id, lang),
                parse_mode="HTML",
            )
            related_ids = []

        # ❌ 1 daqiqalik "Buyurtmani bekor qilish" tugmasi
        from utils.order_cancel import send_customer_cancel_button
        await send_customer_cancel_button(message.bot, user_id, order_id, lang,
                                          related_message_ids=related_ids)

        log.info(
            f"WebApp buyurtma yaratildi: #{order_id}, user={user_id}, "
            f"type={delivery_type}, total={total_amount}"
        )

    except json.JSONDecodeError:
        log.error("WebApp: JSON parse xatosi")
        try:
            lang = await get_user_language(message.from_user.id)
            await message.answer(get_text("webapp_cart_empty", lang))
        except Exception:
            pass
    except Exception as e:
        log.error(f"WebApp buyurtma xatosi: {e}", exc_info=True)
        try:
            lang = await get_user_language(message.from_user.id)
            await message.answer("⚠️ Buyurtmada xato yuz berdi. Iltimos qayta urinib ko'ring.")
        except Exception:
            pass


def register_webapp_menu_handlers(dp: Dispatcher):
    """
    WebApp cart/order handlerini ro'yxatdan o'tkazadi.
    register_order_handlers() DAN KEYIN chaqirilishi kerak.
    """
    dp.register_message_handler(
        process_webapp_cart,
        _is_webapp_cart,
        content_types=ContentTypes.WEB_APP_DATA,
        state="*",
    )
