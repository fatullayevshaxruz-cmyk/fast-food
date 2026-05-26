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

MUHIM:
  - PAYMENT_PROVIDER_TOKEN .env da bo'lmasa → faqat "Naqd" variant ko'rinadi.
  - Barcha xatoliklar ushlanib, foydalanuvchiga tushunarli xabar beriladi.
  - asyncio.create_task() ishlatiladi — bot sekinlashmaydi.
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
    get_cart_items, create_order, add_order_items, clear_cart
)
from utils.states import OrderStates
from utils.helpers import notify_admins_new_order
from keyboards.main_menu import get_user_main_menu, get_admin_main_menu
from config import ADMIN_ID

log = logging.getLogger(__name__)


# ── Yordamchi funksiyalar ─────────────────────────────────────────────

def _get_menu_for_user(user_id):
    """Admin yoki oddiy foydalanuvchi menyusini qaytaradi."""
    is_admin = str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return get_admin_main_menu() if is_admin else get_user_main_menu()


def _has_payment_token() -> bool:
    """PAYMENT_PROVIDER_TOKEN mavjud va bo'sh emasligini tekshiradi."""
    return bool(PAYMENT_PROVIDER_TOKEN and PAYMENT_PROVIDER_TOKEN.strip())


def _build_payload(user_id: int, order_data: dict) -> str:
    """
    Invoice payload — to'lov muvaffaqiyatli bo'lganda order ma'lumotlarini
    qayta tiklash uchun ishlatiladi.
    Format: "user_id:delivery_type:address:phone:note:discount_pct:promo"
    """
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
    """Payloadni qayta parse qilish."""
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
    """
    Foydalanuvchiga to'lov usulini tanlashni taklif qiladi.
    Agar PAYMENT_PROVIDER_TOKEN yo'q bo'lsa — avtomatik naqd to'lovga o'tadi.
    """
    # Token bo'lmasa — to'lov tanlash oynasini ko'rsatmasdan naqd to'lovga o'tamiz
    if not _has_payment_token():
        log.info("PAYMENT_PROVIDER_TOKEN topilmadi — naqd to'lovga o'tilmoqda.")
        from handlers.order import finish_order
        await finish_order(message, state, payment_method="Naqd (Yetkazib berilganda)")
        return

    await OrderStates.waiting_for_payment_method.set()

    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        KeyboardButton("💵 Naqd pul (Yetkazib berilganda)"),
        KeyboardButton("💳 Online to'lov (Click / Payme)"),
        KeyboardButton("❌ Bekor qilish"),
    )
    await message.answer(
        "💰 <b>To'lov usulini tanlang:</b>\n\n"
        "  💵 <b>Naqd pul</b> — kuryer yetkazib kelganda to'lanadi\n"
        "  💳 <b>Online</b> — Click yoki Payme orqali hozir to'lang",
        reply_markup=markup,
        parse_mode="HTML",
    )


# ── To'lov usuli tanlandi ─────────────────────────────────────────────

async def process_payment_cash(message: types.Message, state: FSMContext):
    """Naqd to'lov tanlandi — mavjud finish_order ga uzatiladi."""
    from handlers.order import finish_order
    await finish_order(message, state, payment_method="Naqd (Yetkazib berilganda)")


async def process_payment_online(message: types.Message, state: FSMContext):
    """Online to'lov tanlandi — Telegram Invoice yuboriladi."""
    try:
        user_id = message.from_user.id
        data = await state.get_data()

        items = await get_cart_items(user_id)
        if not items:
            await message.answer(
                "⚠️ Savatingiz bo'shab qoldi. Qaytadan mahsulot tanlang.",
                reply_markup=_get_menu_for_user(user_id),
            )
            await state.finish()
            return

        # Summalarni hisoblash
        items_total   = sum(i['price'] * i['quantity'] for i in items)
        discount_pct  = data.get("discount_percent", 0)
        discount_amt  = int(items_total * discount_pct / 100) if discount_pct > 0 else 0
        after_discount = items_total - discount_amt
        delivery_type  = data.get("delivery_type", "delivery")
        delivery_fee   = DELIVERY_FEE if delivery_type == "delivery" else 0
        total_amount   = after_discount + delivery_fee

        if total_amount <= 0:
            await message.answer("⚠️ Buyurtma summasi noto'g'ri. Iltimos, qaytadan urinib ko'ring.")
            await state.finish()
            return

        # Telegram Payments UZS uchun summani TIYIN da qabul qiladi.
        # 1 so'm = 100 tiyin, shuning uchun × 100 qilamiz.
        # Misol: 50,000 so'm → 5,000,000 tiyin → Telegram "50,000 so'm" ko'rsatadi.
        prices = [LabeledPrice(label="Buyurtma", amount=total_amount * 100)]

        payload = _build_payload(user_id, data)

        # state ni finish qilmaymiz — successful_payment kelguncha saqlaymiz
        # Lekin payment_method ni state ga yozib qo'yamiz
        await state.update_data(payment_method="Online (Click/Payme)")

        await message.bot.send_invoice(
            chat_id=user_id,
            title="🍔 Fast Food Buyurtmasi",
            description=(
                f"Buyurtmangiz: {len(items)} ta mahsulot\n"
                f"Jami: {total_amount:,} so'm"
            ),
            payload=payload,
            provider_token=PAYMENT_PROVIDER_TOKEN,
            currency="UZS",
            prices=prices,
            start_parameter="fastfood_payment",
            # Opsional sozlamalar
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
            protect_content=False,
        )

        # Invoice yuborilgandan keyin foydalanuvchiga yo'riqnoma
        from aiogram.types import ReplyKeyboardRemove
        await message.answer(
            "💳 <b>To'lov oynasi yuborildi.</b>\n\n"
            "Yuqoridagi kartochkaga bosib to'lovni amalga oshiring.\n"
            "<i>To'lovni bekor qilish uchun oynani yoping.</i>",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )

    except Exception as e:
        log.error(f"Invoice yuborishda xatolik: {e}", exc_info=True)
        await message.answer(
            "⚠️ Online to'lovni boshlashda xatolik yuz berdi.\n"
            "Iltimos, <b>Naqd pul</b> usulini tanlang yoki qaytadan urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=_get_menu_for_user(message.from_user.id),
        )
        await state.finish()


# ── Pre-Checkout Query (Telegram majburiy talabi) ─────────────────────

async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """
    Telegram to'lovni tasdiqlashdan oldin bu handlerni chaqiradi.
    10 soniya ichida answer_pre_checkout_query() chaqirilishi SHART.
    """
    try:
        # Payload ni tekshirishimiz mumkin, lekin oddiy holda ok=True
        await pre_checkout_query.bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=True,
        )
        log.info(f"PreCheckoutQuery OK: user_id={pre_checkout_query.from_user.id}")
    except Exception as e:
        log.error(f"PreCheckoutQuery xatosi: {e}", exc_info=True)
        # Xatolik bo'lsa ham reject qilamiz (foydalanuvchi qaytadan urinishi mumkin)
        try:
            await pre_checkout_query.bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="To'lovni tasdiqlashda xatolik. Qaytadan urinib ko'ring.",
            )
        except Exception:
            pass


# ── Successful Payment ────────────────────────────────────────────────

async def process_successful_payment(message: types.Message, state: FSMContext):
    """
    To'lov muvaffaqiyatli bo'lganda chaqiriladi.
    Order bazaga yoziladi va admin xabardor qilinadi.
    """
    try:
        user_id = message.from_user.id
        payment = message.successful_payment
        payload = payment.invoice_payload

        # Payload dan order ma'lumotlarini olish
        order_data = _parse_payload(payload)

        # State dan qo'shimcha ma'lumotlar (agar hali saqlab turilgan bo'lsa)
        state_data = await state.get_data()
        delivery_type  = order_data.get("delivery_type") or state_data.get("delivery_type", "delivery")
        address        = order_data.get("address") or state_data.get("address", "")
        phone          = order_data.get("phone") or state_data.get("phone")
        note           = order_data.get("note") or state_data.get("note")
        discount_pct   = order_data.get("discount_percent", 0) or state_data.get("discount_percent", 0)
        promo_code     = order_data.get("promo_code") or state_data.get("promo_code")
        lat            = state_data.get("lat")
        lon            = state_data.get("lon")

        # Telegram payment.total_amount ni TIYIN da beradi (UZS: ×100 qilingan edi).
        # Bazaga SO'MDA yozish uchun ÷100 qilamiz.
        total_amount = payment.total_amount // 100

        # Agar state allaqachon tozalangan bo'lsa — savat ma'lumotlaridan olamiz
        items = await get_cart_items(user_id)

        if not items:
            # Savat bo'sh (ikkinchi marta signal keldi yoki muammo bor)
            log.warning(f"SuccessfulPayment: savat bo'sh, user_id={user_id}")
            await message.answer(
                "✅ <b>To'lov qabul qilindi!</b>\n\n"
                "Buyurtmangiz tez orada qayta ishlanadi.\n"
                "Aloqa uchun adminga murojaat qiling.",
                reply_markup=_get_menu_for_user(user_id),
                parse_mode="HTML",
            )
            await state.finish()
            return

        # Order yaratish
        order_id = await create_order(
            user_id=user_id,
            total_amount=total_amount,
            address=address if address else "Noma'lum",
            payment_method="Online (Click/Payme)",
            latitude=lat,
            longitude=lon,
            phone_number=phone,
            note=note,
            delivery_type=delivery_type,
        )
        await add_order_items(order_id, items)
        await clear_cart(user_id)

        await state.finish()

        # Admin xabardor qilish — background da (foydalanuvchini kutdirmaydi)
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
            payment_method="Online (Click/Payme)",
        ))

        # Chek matni
        receipt = "".join(
            f"  ▫️ {i['name']} x {i['quantity']} = {i['price'] * i['quantity']:,} so'm\n"
            for i in items
        )

        if delivery_type == "eat_in":
            result_text = (
                f"✅ <b>To'lov qabul qilindi va buyurtma tasdiqlandi!</b>\n\n"
                f"📋 <b>Buyurtma #{order_id}</b>\n"
                f"🍽️ <b>Shu yerda</b> | {address}\n\n"
                f"{receipt}"
                f"  💰 <b>Jami: {total_amount:,} so'm</b>\n\n"
                f"💳 <i>Online to'lov: {payment.provider_payment_charge_id}</i>\n\n"
                f"🍖 Ofitsiant olib keladi. Yoqimli ishtaha! 😋"
            )
        else:
            result_text = (
                f"✅ <b>To'lov qabul qilindi va buyurtma tasdiqlandi!</b>\n\n"
                f"📋 <b>Buyurtma #{order_id}</b>\n"
                f"🛵 <b>Yetkazib berish</b>\n\n"
                f"{receipt}"
                f"  💰 <b>Jami: {total_amount:,} so'm</b>\n\n"
                f"💳 <i>Online to'lov amalga oshirildi</i>\n\n"
                f"🛵 Yetkazib beruvchi siz bilan bog'lanadi.\n"
                f"Rahmat! Yoqimli ishtaha! 😋"
            )

        await message.answer(
            result_text,
            reply_markup=_get_menu_for_user(user_id),
            parse_mode="HTML",
        )

    except Exception as e:
        log.error(f"SuccessfulPayment xatosi: {e}", exc_info=True)
        await message.answer(
            "✅ To'lovingiz qabul qilindi!\n\n"
            "⚠️ Buyurtmani qayta ishlashda kichik muammo yuz berdi.\n"
            "Tez orada siz bilan bog'lanamiz.",
            reply_markup=_get_menu_for_user(message.from_user.id),
            parse_mode="HTML",
        )
        # State ni tozalash
        try:
            await state.finish()
        except Exception:
            pass


# ── Handlerlarni ro'yxatdan o'tkazish ────────────────────────────────

def register_payment_handlers(dp: Dispatcher):
    """
    Barcha to'lov handlerlarini ro'yxatdan o'tkazadi.
    MUHIM: PreCheckoutQuery va SuccessfulPayment — state mustaqil ishlaydi.
    """
    # 1. To'lov usulini tanlash (faqat waiting_for_payment_method holatida)
    dp.register_message_handler(
        process_payment_cash,
        text="💵 Naqd pul (Yetkazib berilganda)",
        state=OrderStates.waiting_for_payment_method,
    )
    dp.register_message_handler(
        process_payment_online,
        text="💳 Online to'lov (Click / Payme)",
        state=OrderStates.waiting_for_payment_method,
    )

    # 2. PreCheckoutQuery — Telegram majburiy (state=None: istalgan holatda)
    dp.register_pre_checkout_query_handler(
        process_pre_checkout,
        lambda q: True,  # barcha pre_checkout so'rovlarni qabul qilish
    )

    # 3. SuccessfulPayment — state=None (istalgan holat)
    dp.register_message_handler(
        process_successful_payment,
        content_types=types.ContentTypes.SUCCESSFUL_PAYMENT,
        state="*",
    )
