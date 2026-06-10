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
    get_cart_items, create_order, add_order_items, clear_cart, get_user_language
)
from utils.states import OrderStates
from utils.helpers import notify_admins_new_order
from utils.i18n import get_text
from keyboards.main_menu import get_user_main_menu, get_admin_main_menu
from config import ADMIN_ID

log = logging.getLogger(__name__)


# ── Yordamchi funksiyalar ─────────────────────────────────────────────

async def _get_menu_for_user(user_id):
    """Admin yoki oddiy foydalanuvchi menyusini qaytaradi."""
    lang = await get_user_language(user_id)
    is_admin = str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return get_admin_main_menu(lang) if is_admin else get_user_main_menu(lang)


def _has_payment_token() -> bool:
    return bool(PAYMENT_PROVIDER_TOKEN and PAYMENT_PROVIDER_TOKEN.strip())


def _build_payload(user_id: int, order_data: dict) -> str:
    parts = [
        str(user_id),
        order_data.get("delivery_type", "delivery"),
        (order_data.get("address") or "").replace(":", "-"),
        (order_data.get("phone") or ""),
        (order_data.get("note") or "").replace(":", "-"),
        str(order_data.get("discount_percent", 0)),
        (order_data.get("promo_code") or ""),
    ]
    return ":".join(parts)


def _parse_payload(payload: str) -> dict:
    parts = payload.split(":", 6)
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
    lang = await get_user_language(message.from_user.id)

    if not _has_payment_token():
        log.info("PAYMENT_PROVIDER_TOKEN topilmadi — naqd to'lovga o'tilmoqda.")
        from handlers.order import finish_order
        await finish_order(message, state, payment_method=get_text("btn_pay_cash", lang))
        return

    await OrderStates.waiting_for_payment_method.set()

    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        KeyboardButton(get_text("btn_pay_cash", lang)),
        KeyboardButton(get_text("btn_pay_online", lang)),
        KeyboardButton(get_text("btn_cancel", lang)),
    )
    await message.answer(
        get_text("ask_payment_method", lang),
        reply_markup=markup,
        parse_mode="HTML",
    )


# ── To'lov usuli tanlandi ─────────────────────────────────────────────

async def process_payment_cash(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    from handlers.order import finish_order
    await finish_order(message, state, payment_method=get_text("btn_pay_cash", lang))


async def process_payment_online(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
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
        delivery_fee   = DELIVERY_FEE if delivery_type == "delivery" else 0
        total_amount   = after_discount + delivery_fee

        if total_amount <= 0:
            await message.answer(get_text("invalid_amount", lang))
            await state.finish()
            return

        prices = [LabeledPrice(label="Buyurtma", amount=total_amount * 100)]
        payload = _build_payload(user_id, data)
        await state.update_data(payment_method=get_text("btn_pay_online", lang))

        if lang == "ru":
            inv_title = "🍔 Fast Food — Заказ"
            inv_desc = f"Товаров: {len(items)} шт.\nИтого: {total_amount:,} сум"
        elif lang == "en":
            inv_title = "🍔 Fast Food — Order"
            inv_desc = f"Items: {len(items)}\nTotal: {total_amount:,} sum"
        else:
            inv_title = "🍔 Fast Food Buyurtmasi"
            inv_desc = f"Buyurtmangiz: {len(items)} ta mahsulot\nJami: {total_amount:,} so'm"

        await message.bot.send_invoice(
            chat_id=user_id,
            title=inv_title,
            description=inv_desc,
            payload=payload,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="UZS",
            prices=prices,
            start_parameter="fastfood_payment",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
            protect_content=False,
        )

        from aiogram.types import ReplyKeyboardRemove
        await message.answer(
            get_text("invoice_sent", lang),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )

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
    try:
        await pre_checkout_query.bot.answer_pre_checkout_query(
            pre_checkout_query.id, ok=True,
        )
        log.info(f"PreCheckoutQuery OK: user_id={pre_checkout_query.from_user.id}")
    except Exception as e:
        log.error(f"PreCheckoutQuery xatosi: {e}", exc_info=True)
        lang = await get_user_language(pre_checkout_query.from_user.id)
        try:
            await pre_checkout_query.bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message=get_text("precheckout_error", lang),
            )
        except Exception:
            pass


# ── Successful Payment ────────────────────────────────────────────────

async def process_successful_payment(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    try:
        user_id = message.from_user.id
        payment = message.successful_payment
        payload = payment.invoice_payload

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

        order_id = await create_order(
            user_id=user_id,
            total_amount=total_amount,
            address=address if address else "Noma'lum",
            payment_method=get_text("btn_pay_online", lang),
            latitude=lat,
            longitude=lon,
            phone_number=phone,
            note=note,
            delivery_type=delivery_type,
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
            payment_method=get_text("btn_pay_online", lang),
        ))

        # Chek matn (til bo'yicha)
        receipt = "".join(
            get_text("item_line", lang, name=i['name'], qty=i['quantity'],
                     total=i['price'] * i['quantity']) + "\n"
            for i in items
        )

        if delivery_type == "eat_in":
            result_text = get_text(
                "payment_accepted_eat_in", lang,
                order_id=order_id, address=address,
                receipt=receipt, total=total_amount,
                charge_id=payment.provider_payment_charge_id
            )
        else:
            result_text = get_text(
                "payment_accepted_delivery", lang,
                order_id=order_id, receipt=receipt, total=total_amount
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


# ── Handlerlarni ro'yxatdan o'tkazish ────────────────────────────────

def register_payment_handlers(dp: Dispatcher):
    # To'lov tugmalarining barcha 3 tildagi variantlari
    _CASH_TEXTS   = [
        "💵 Naqd pul (Yetkazib berilganda)",
        "💵 Наличные (При получении)",
        "💵 Cash (On Delivery)",
    ]
    _ONLINE_TEXTS = [
        "💳 Online to'lov (Click / Payme)",
        "💳 Онлайн (Click / Payme)",
        "💳 Online (Click / Payme)",
    ]

    dp.register_message_handler(
        process_payment_cash,
        lambda m: m.text in _CASH_TEXTS,
        state=OrderStates.waiting_for_payment_method,
    )
    dp.register_message_handler(
        process_payment_online,
        lambda m: m.text in _ONLINE_TEXTS,
        state=OrderStates.waiting_for_payment_method,
    )
    dp.register_pre_checkout_query_handler(
        process_pre_checkout,
        lambda q: True,
    )
    dp.register_message_handler(
        process_successful_payment,
        content_types=types.ContentTypes.SUCCESSFUL_PAYMENT,
        state="*",
    )
