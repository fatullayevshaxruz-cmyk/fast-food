"""
handlers/payment.py
===================
Telegram Payments API orqali Click / Payme to'lov tizimi.

Oqim:
  ask_payment_method()          ← process_promo / process_note (eat_in emas) dan chaqiriladi
       ↓
  💵 Naqd → finish_order()      ← mavjud funksiya, o'zgarishsiz
  💳 Online → send_invoice()    ← Telegram Invoice yuboriladi
       ↓
  pre_checkout_query handler    ← Telegram majburiy tekshirish (10s ichida ok=True)
       ↓
  successful_payment handler    ← order bazaga yoziladi, admin xabardor
"""

import asyncio
import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery,
)

from config import PAYMENT_PROVIDER_TOKEN, DELIVERY_FEE
from database.crud import (
    get_cart_items, create_order, add_order_items, clear_cart, get_user_language,
    get_product_name
)
from utils.states import OrderStates
from utils.helpers import notify_admins_new_order
from utils.i18n import get_text
from keyboards.main_menu import get_user_main_menu, get_admin_main_menu
from config import ADMIN_ID
from security.payment_guard import (
    sign_invoice_payload,
    verify_and_strip_invoice_payload,
    is_transaction_already_used,
    mark_transaction_used,
    verify_cart_payment_amount,
)

log = logging.getLogger(__name__)

# Bazaga va admin kanaliga yoziladigan to'lov usuli nomlari (tildan qat'i nazar bir xil).
# "Online" so'zi utils/helpers.py da karta to'lovini aniqlash uchun ishlatiladi.
CASH_METHOD   = "💵 Naqd (Yetkazib berilganda)"
ONLINE_METHOD = "💳 Online to'lov (Karta)"


# ── Yordamchi funksiyalar ─────────────────────────────────────────────

async def _get_menu_for_user(user_id):
    """Admin yoki oddiy foydalanuvchi menyusini qaytaradi."""
    lang = await get_user_language(user_id)
    is_admin = str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return get_admin_main_menu(lang) if is_admin else get_user_main_menu(lang)


def _has_payment_token() -> bool:
    return bool(PAYMENT_PROVIDER_TOKEN and PAYMENT_PROVIDER_TOKEN.strip())


def _get_bot():
    try:
        from aiogram import Bot
        b = Bot.get_current()
        if b:
            return b
    except Exception:
        pass
    try:
        from bot import bot as main_bot
        return main_bot
    except Exception:
        return None


def _build_payload(user_id: int, order_data: dict) -> str:
    parts = [
        str(user_id),
        order_data.get("delivery_type", "delivery"),
        (order_data.get("address") or "")[:20].replace(":", "-").replace("|", "-"),
        (order_data.get("phone") or "")[:16],
        (order_data.get("note") or "")[:15].replace(":", "-").replace("|", "-"),
        str(order_data.get("discount_percent", 0)),
        (order_data.get("promo_code") or "")[:15],
    ]
    raw = ":".join(parts)
    return sign_invoice_payload(raw)


def _parse_payload(payload: str) -> dict:
    # HMAC-SHA256 imzoni tekshirish va olib tashlash
    is_valid, clean_payload = verify_and_strip_invoice_payload(payload)
    if not is_valid:
        raise ValueError("Soxta to'lov payload imzosi (HMAC verification failed)")

    # WebApp invoice: "webapp:user_id:delivery_type:discount_percent:promo_code"
    # Manzil, telefon va boshqalar FSM state dan olinadi
    if clean_payload.startswith("webapp:"):
        parts = clean_payload.split(":", 4)
        parts += [""] * (5 - len(parts))
        return {
            "user_id": int(parts[1] or 0),
            "delivery_type": parts[2],
            "address": "",
            "phone": "",
            "note": "",
            "discount_percent": int(parts[3] or 0),
            "promo_code": parts[4],
        }

    parts = clean_payload.split(":", 6)
    keys = ["user_id", "delivery_type", "address", "phone", "note",
            "discount_percent", "promo_code"]
    result = {}
    for i, key in enumerate(keys):
        result[key] = parts[i] if i < len(parts) else ""
    result["discount_percent"] = int(result["discount_percent"] or 0)
    result["user_id"] = int(result["user_id"])
    return result


# ── To'lov usulini so'rash ────────────────────────────────────────────

async def ask_payment_method(message: types.Message, state: FSMContext):
    from utils.payment_links import is_online_payment_available
    lang = await get_user_language(message.from_user.id)

    await OrderStates.waiting_for_payment_method.set()

    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    # 💳 Karta (online to'lov) faqat Payme yoki Click haqiqiy ID'lari sozlangan bo'lsa ko'rsatiladi
    if is_online_payment_available():
        markup.row(
            KeyboardButton(get_text("btn_pay_cash", lang)),
            KeyboardButton(get_text("btn_pay_online", lang)),
        )
    else:
        log.info("Online to'lov yashirildi: PAYME_MERCHANT_ID / CLICK_MERCHANT_ID sozlanmagan")
        markup.add(KeyboardButton(get_text("btn_pay_cash", lang)))

    markup.add(KeyboardButton(get_text("btn_cancel", lang)))

    await message.answer(
        get_text("ask_payment_method", lang),
        reply_markup=markup,
        parse_mode="HTML",
    )


# ── To'lov usuli tanlandi ─────────────────────────────────────────────

async def process_payment_cash(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    from handlers.order import finish_order
    await finish_order(message, state, payment_method=CASH_METHOD)


async def process_payment_online(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)

    # Eski klaviaturasi qolgan mijozlar uchun: online to'lov sozlanmagan bo'lsa buyurtma yaratilmaydi
    from utils.payment_links import is_online_payment_available
    if not is_online_payment_available():
        await message.answer(
            "⚠️ Online to'lov vaqtincha mavjud emas. Iltimos, naqd to'lovni tanlang."
            if lang == "uz" else
            ("⚠️ Онлайн-оплата временно недоступна. Пожалуйста, выберите оплату наличными."
             if lang == "ru" else
             "⚠️ Online payment is temporarily unavailable. Please choose cash."),
        )
        await ask_payment_method(message, state)
        return

    try:
        user_id = message.from_user.id
        data = await state.get_data()

        items = await get_cart_items(user_id)
        if not items:
            await message.answer(
                get_text("cart_empty_retry", lang),
                reply_markup=await _get_menu_for_user(user_id),
            )
            await state.finish()
            return

        items_total   = sum(i['price'] * i['quantity'] for i in items)
        discount_pct  = data.get("discount_percent", 0)
        discount_amt  = int(items_total * discount_pct / 100) if discount_pct > 0 else 0
        after_discount = items_total - discount_amt
        delivery_type  = data.get("delivery_type", "delivery")

        # ── Masofaga qarab yetkazish narxi ─────────────────────────
        if delivery_type == "delivery":
            lat = data.get("lat")
            lon = data.get("lon")
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

        if total_amount <= 0:
            await message.answer(get_text("invalid_amount", lang))
            await state.finish()
            return

        address = data.get("address") or "Manzil kiritilmagan"
        phone = data.get("phone")
        note = data.get("note")
        promo_code = data.get("promo_code")
        lat = data.get("lat")
        lon = data.get("lon")
        branch_id = data.get("branch_id")
        branch_name = data.get("branch_name")
        distance_km = data.get("distance_km")

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

        # ── Buyurtmani bazada yaratish ─────────────────────────────
        order_id = await create_order(
            user_id=user_id,
            total_amount=total_amount,
            address=address,
            payment_method=ONLINE_METHOD,
            latitude=lat,
            longitude=lon,
            phone_number=phone,
            note=note,
            delivery_type=delivery_type,
            promo_code=promo_code,
            discount_amount=discount_amt,
            branch_id=branch_id,
            branch_name=branch_name,
            distance_km=distance_km,
        )
        await add_order_items(order_id, items)
        await clear_cart(user_id)
        await state.finish()

        # ── Click va Payme to'lov havolalari (Deep Links) — faqat sozlanganlari ──
        from utils.payment_links import build_pay_keyboard

        pay_kb = build_pay_keyboard(order_id, total_amount)

        # ── DIQQAT: Toki to'lov amalga oshirilmaguncha filial kanaliga YUBORILMAYDI! ──
        # To'lov Payme/Click webhook yoki 'To'lovni tekshirish' tugmasi orqali
        # tasdiqlangach, dispatch_paid_order_to_channel orqali kanalga yuboriladi.

        # Chek (til bo'yicha)
        receipt = "".join(
            get_text("item_line", lang, name=get_product_name(i, lang), qty=i['quantity'],
                     total=i['price'] * i['quantity']) + "\n"
            for i in items
        )

        note_text = f"\n  📝 <i>{note}</i>" if note else ""
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

        pay_prompt = (
            "\n\n⏳ <b>DIQQAT:</b> Buyurtmangiz oshxonaga qabul qilinishi uchun to'lovni amalga oshiring.\n"
            "👇 <i>To'lov amalga oshirilgach, buyurtma darhol oshxona kanaliga yuboriladi:</i>"
            if lang == "uz"
            else ("\n\n⏳ <b>ВНИМАНИЕ:</b> Чтобы заказ поступил на кухню, совершите оплату.\n"
                  "👇 <i>После оплаты заказ сразу поступит на кухню:</i>" if lang == "ru"
                  else "\n\n⏳ <b>NOTE:</b> Please complete payment to submit your order to the kitchen.\n"
                       "👇 <i>Order will be forwarded to the kitchen once paid:</i>")
        )

        # Foydalanuvchiga chek va to'lov havolalarini yuborish
        pay_msg = await message.answer(
            success_text + pay_prompt,
            reply_markup=pay_kb,
            parse_mode="HTML",
        )

        # Asosiy menyu klaviaturasini qayta chiqarish
        menu_kb = await _get_menu_for_user(user_id)
        await message.answer(
            "🍔 Asosiy menyu:" if lang == "uz" else ("🍔 Главное меню:" if lang == "ru" else "🍔 Main menu:"),
            reply_markup=menu_kb,
        )

        # ❌ 1 daqiqalik "Buyurtmani bekor qilish" tugmasi
        from utils.order_cancel import send_customer_cancel_button
        await send_customer_cancel_button(message.bot, user_id, order_id, lang,
                                          related_message_ids=[pay_msg.message_id])

    except Exception as e:
        log.error(f"Invoice yuborishda xatolik: {e}", exc_info=True)
        await message.answer(
            get_text("payment_error", lang),
            parse_mode="HTML",
            reply_markup=await _get_menu_for_user(message.from_user.id),
        )
        await state.finish()


# ── Pre-Checkout Query ────────────────────────────────────────────────

async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    b = getattr(pre_checkout_query, 'bot', None) or _get_bot()
    try:
        user_id = pre_checkout_query.from_user.id
        # 1. Payload HMAC imzosini va user_id mosligini tekshirish
        try:
            order_data = _parse_payload(pre_checkout_query.invoice_payload)
        except Exception as sig_err:
            log.warning(f"🚨 PreCheckout: Soxta payload! user_id={user_id}, err={sig_err}")
            await b.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="To'lov imzosi noto'g'ri (Xavfsizlik tekshiruvidan o'tmadi).",
            )
            return

        if order_data.get("user_id") and int(order_data["user_id"]) != user_id:
            log.warning(f"🚨 PreCheckout: User ID mos kelmadi! payload={order_data.get('user_id')}, actual={user_id}")
            await b.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="Foydalanuvchi identifikatori mos kelmadi.",
            )
            return

        # 2. Bazadagi mahsulot narxlari bilan to'lov summasini solishtirish
        ok_amount, reason, _ = await verify_cart_payment_amount(
            user_id=user_id,
            paid_amount_tiyin=pre_checkout_query.total_amount,
            currency=pre_checkout_query.currency,
            discount_pct=order_data.get("discount_percent", 0),
            promo_code=order_data.get("promo_code") or None,
        )
        if not ok_amount:
            await b.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message=reason,
            )
            return

        await b.answer_pre_checkout_query(
            pre_checkout_query.id, ok=True,
        )
        log.info(f"✅ PreCheckoutQuery OK: id={pre_checkout_query.id}, user_id={user_id}")
    except Exception as e:
        log.error(f"❌ PreCheckoutQuery xatosi: {e}", exc_info=True)
        try:
            lang = await get_user_language(pre_checkout_query.from_user.id)
            await b.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message=get_text("precheckout_error", lang),
            )
        except Exception as e2:
            log.error(f"❌ PreCheckoutQuery fallback xatosi: {e2}")


# ── Successful Payment ────────────────────────────────────────────────

async def process_successful_payment(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    try:
        user_id = message.from_user.id
        payment = message.successful_payment
        payload = payment.invoice_payload
        tx_id   = payment.provider_payment_charge_id

        # 1. Replay / Double-Spend (bitta tranzaksiyani 2 marta o'tkazish) himoyasi
        if await is_transaction_already_used(tx_id):
            log.warning(f"🚨 Replay Payment Attack to'xtatildi: tx_id={tx_id}, user_id={user_id}")
            return

        order_data    = _parse_payload(payload)
        state_data    = await state.get_data()
        delivery_type = order_data.get("delivery_type") or state_data.get("delivery_type", "delivery")
        address       = order_data.get("address") or state_data.get("address", "")
        phone         = order_data.get("phone") or state_data.get("phone")
        note          = order_data.get("note") or state_data.get("note")
        discount_pct  = order_data.get("discount_percent", 0) or state_data.get("discount_percent", 0)
        promo_code    = order_data.get("promo_code") or state_data.get("promo_code")
        lat           = state_data.get("lat")
        lon           = state_data.get("lon")
        total_amount  = payment.total_amount // 100

        items = await get_cart_items(user_id)

        if not items:
            log.warning(f"SuccessfulPayment: savat bo'sh, user_id={user_id}")
            await message.answer(
                get_text("payment_accepted_empty_cart", lang),
                reply_markup=await _get_menu_for_user(user_id),
                parse_mode="HTML",
            )
            await state.finish()
            return

        mark_transaction_used(tx_id)
        items_total    = sum(i['price'] * i['quantity'] for i in items)
        discount_amt   = int(items_total * discount_pct / 100) if discount_pct > 0 else 0
        after_discount = items_total - discount_amt
        delivery_fee   = max(0, total_amount - after_discount) if delivery_type == "delivery" else 0

        branch_id   = state_data.get("branch_id")
        branch_name = state_data.get("branch_name")
        distance_km = state_data.get("distance_km")
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

        order_id = await create_order(
            user_id=user_id,
            total_amount=total_amount,
            address=address if address else "Noma'lum",
            payment_method=ONLINE_METHOD,
            latitude=lat,
            longitude=lon,
            phone_number=phone,
            note=note,
            delivery_type=delivery_type,
            payment_status="paid",
            transaction_id=tx_id,
            promo_code=promo_code,
            discount_amount=discount_amt,
            branch_id=branch_id,
            branch_name=branch_name,
            distance_km=distance_km,
        )
        await add_order_items(order_id, items)
        await clear_cart(user_id)
        await state.finish()

        asyncio.create_task(notify_admins_new_order(
            bot=message.bot,
            order_id=order_id,
            total_amount=total_amount,
            user=message.from_user,
            items=items,
            phone=phone,
            address=address,
            location={"lat": lat, "lon": lon},
            note=note,
            delivery_type=delivery_type,
            payment_method=ONLINE_METHOD,
            promo_code=promo_code,
            discount_pct=discount_pct,
            discount_amt=discount_amt,
            branch_name=branch_name,
            distance_km=distance_km,
        ))

        # Chek matn (til bo'yicha)
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
            result_text = get_text(
                "payment_accepted_eat_in", lang,
                order_id=order_id, address=address,
                receipt=receipt, discount=discount_text,
                total=total_amount,
                charge_id=payment.provider_payment_charge_id
            )
        else:
            result_text = get_text(
                "payment_accepted_delivery", lang,
                order_id=order_id, receipt=receipt,
                discount=discount_text,
                delivery_fee=delivery_fee,
                total=total_amount
            )

        await message.answer(
            result_text,
            reply_markup=await _get_menu_for_user(user_id),
            parse_mode="HTML",
        )

    except Exception as e:
        log.error(f"SuccessfulPayment xatosi: {e}", exc_info=True)
        lang2 = await get_user_language(message.from_user.id)
        await message.answer(
            get_text("payment_generic_error", lang2),
            reply_markup=await _get_menu_for_user(message.from_user.id),
            parse_mode="HTML",
        )
        try:
            await state.finish()
        except Exception:
            pass


async def check_payment_callback(call: types.CallbackQuery):
    """
    Mijoz botda 'To'lovni tekshirish' tugmasini bosganda.
    Haqiqiy to'lov holatini bazadan tekshiradi:
    Toki Click yoki Payme rasmiy webhooki to'lovni tasdiqlamagan bo'lsa,
    kanalga ASLO yuborilmaydi!
    """
    try:
        order_id = int(call.data.split("_")[2])
    except Exception:
        await call.answer("Buyurtma topilmadi", show_alert=True)
        return

    from database.crud import get_order_by_id
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("⚠️ Buyurtma topilmadi!", show_alert=True)
        return

    order_d = dict(order)
    payment_status = str(order_d.get("payment_status") or "unpaid")

    if order_d.get("status") == "cancelled" and payment_status != "paid":
        await call.answer("❌ Bu buyurtma bekor qilingan.", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if payment_status == "paid":
        from utils.order_dispatcher import dispatch_paid_order_to_channel
        await dispatch_paid_order_to_channel(call.bot, order_id)
        await call.answer("✅ To'lovingiz tasdiqlangan! Buyurtma oshxonada tayyorlanmoqda.", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await call.answer(
            "❌ To'lov hali hisobingizdan yechilmadi yoki Click/Payme tomonidan tasdiqlanmadi.\n\n"
            "Iltimos, avval Click yoki Payme ilovasida to'lovni bajaring!",
            show_alert=True,
        )


# ── Handlerlarni ro'yxatdan o'tkazish ────────────────────────────────

def register_payment_handlers(dp: Dispatcher):
    # To'lov tugmalarining barcha 3 tildagi variantlari
    _LANGS = ("uz", "ru", "en")
    _CASH_TEXTS = {get_text("btn_pay_cash", l) for l in _LANGS} | {
        # eski tugma matnlari (eski klaviaturasi qolgan foydalanuvchilar uchun)
        "💵 Naqd pul (Yetkazib berilganda)",
        "💵 Наличные (При получении)",
        "💵 Cash (On Delivery)",
    }
    _ONLINE_TEXTS = {get_text("btn_pay_online", l) for l in _LANGS} | {
        "💳 Online to'lov (Click / Payme)",
        "💳 Онлайн (Click / Payme)",
        "💳 Online (Click / Payme)",
    }

    # Botdagi to'lovni tekshirish tugmasi
    dp.register_callback_query_handler(
        check_payment_callback,
        lambda c: c.data and c.data.startswith("chk_pay_"),
        state="*",
    )

    dp.register_message_handler(
        process_payment_cash,
        lambda m: m.text in _CASH_TEXTS,
        state="*",
    )
    dp.register_message_handler(
        process_payment_online,
        lambda m: m.text in _ONLINE_TEXTS,
        state="*",
    )
    dp.register_pre_checkout_query_handler(
        process_pre_checkout,
        lambda q: True,
        state="*",
    )
    dp.register_message_handler(
        process_successful_payment,
        content_types=types.ContentTypes.SUCCESSFUL_PAYMENT,
        state="*",
    )
