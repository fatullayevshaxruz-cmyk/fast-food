"""
utils/order_dispatcher.py
=========================
To'lov amalga oshirilgandan keyin buyurtmani tegishli filial kanaliga
yo'naltirish (Order Dispatcher) moduli.

Qoida:
  - Naqd (cash) to'lov: buyurtma yaratilishi bilan darhol kanalga yuboriladi.
  - Payme / Click to'lov: TOKI to'lov amalga oshirilmasa (`payment_status = 'paid'`),
    buyurtma kanalga YUBORILMAYDI.
  - To'lov tasdiqlanganda (Webhook yoki tekshirish orqali) `dispatch_paid_order_to_channel`
    chaqirilib, buyurtma tegishli filial kanaliga yuboriladi va mijozga tasdiqnoma boradi.
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from database.crud import (
    get_order_by_id,
    get_order_items_detail,
    get_user,
    get_user_language,
    update_order_payment_status,
)
from utils.geo_routing import route_order_to_nearest_branch
from utils.i18n import get_text

log = logging.getLogger(__name__)

# Takroriy yuborilishdan himoya (Replay protection)
_DISPATCHED_ORDERS = set()


async def dispatch_paid_order_to_channel(
    bot,
    order_id: int,
    transaction_id: Optional[str] = None,
) -> bool:
    """
    To'lov muvaffaqiyatli amalga oshirilganda chaqiriladi:
      1. Bazada `payment_status = 'paid'` qilib yangilaydi.
      2. Buyurtmani tegishli filial kanaliga (1-filial yoki 2-filial) yo'naltiradi.
      3. Mijozga to'lov qabul qilingani va buyurtma oshxonaga yuborilgani haqida xabar beradi.
    """
    if order_id in _DISPATCHED_ORDERS:
        log.info(f"Buyurtma #{order_id} allaqachon kanalga yuborilgan, o'tkazib yuborildi.")
        return True

    order_row = await get_order_by_id(order_id)
    if not order_row:
        log.warning(f"dispatch_paid_order_to_channel: Buyurtma #{order_id} topilmadi.")
        return False

    order = dict(order_row)
    current_status = str(order.get("payment_status") or "unpaid")

    # Qat'iy tekshiruv: Toki to'lov rasman tasdiqlanmagan bo'lsa (payment_status != 'paid' va transaction_id yo'q),
    # kanalga mutlaqo yuborilmaydi!
    if current_status != "paid" and not transaction_id:
        log.warning(f"dispatch_paid_order_to_channel: Buyurtma #{order_id} hali to'lanmagan!")
        return False

    # 1. To'lov holatini 'paid' ga o'tkazish
    try:
        if current_status != "paid" or transaction_id:
            await update_order_payment_status(order_id, "paid", transaction_id=transaction_id)
    except Exception as e:
        log.warning(f"To'lov holatini yangilashda xato: {e}")

    _DISPATCHED_ORDERS.add(order_id)

    # 2. Mahsulotlar va buyurtma tafsilotlarini olish
    items_rows = await get_order_items_detail(order_id)
    items = [dict(r) for r in items_rows] if items_rows else []

    user_id = int(order["user_id"])
    user_row = await get_user(user_id)

    class SimpleUser:
        def __init__(self, uid, name, username=None):
            self.id = uid
            self.full_name = name
            self.username = username

    full_name = order.get("full_name") or (user_row["full_name"] if user_row else "Mijoz")
    username = order.get("username") or (user_row["username"] if user_row else None)
    tg_user = SimpleUser(user_id, full_name, username)

    total_amount = int(order.get("total_amount") or 0)
    address = order.get("delivery_address") or "Manzil kiritilmagan"
    phone = order.get("phone_number") or ""
    note = order.get("note")
    delivery_type = order.get("delivery_type") or "delivery"
    promo_code = order.get("promo_code")
    discount_amt = int(order.get("discount_amount") or 0)
    client_lat = order.get("latitude")
    client_lon = order.get("longitude")
    branch_id = order.get("branch_id")
    payment_method = order.get("payment_method") or "💳 Online to'lov (Payme/Click)"

    # 3. Filial kanaliga yo'naltirish
    try:
        if bot:
            await route_order_to_nearest_branch(
                bot=bot,
                order_id=order_id,
                total_amount=total_amount,
                user=tg_user,
                items=items,
                phone=phone,
                address=address,
                client_lat=client_lat,
                client_lon=client_lon,
                note=note,
                delivery_type=delivery_type,
                payment_method=payment_method,
                promo_code=promo_code,
                discount_amt=discount_amt,
                branch_id=branch_id,
            )
    except Exception as e:
        log.error(f"Buyurtma #{order_id} ni filial kanaliga yo'naltirishda xato: {e}", exc_info=True)

    # 4. Mijozga to'lov muvaffaqiyatli o'tganligi haqida xabar berish
    try:
        if bot:
            lang = await get_user_language(user_id)
            if lang == "ru":
                msg = (
                    f"🎉💳 <b>Оплата успешно получена!</b>\n\n"
                    f"Заказ <b>#{order_id}</b> на сумму <b>{total_amount:,} сум</b> оплачен и передан на кухню <b>Darxan Burger</b>!\n\n"
                    f"👨‍🍳 Наши повара уже начали готовить ваш вкуснейший заказ. "
                    f"Статус заказа вы можете отслеживать в разделе «Заказ»."
                )
            elif lang == "en":
                msg = (
                    f"🎉💳 <b>Payment successfully received!</b>\n\n"
                    f"Order <b>#{order_id}</b> ({total_amount:,} UZS) is paid and sent to <b>Darxan Burger</b> kitchen!\n\n"
                    f"👨‍🍳 We have started preparing your meal. Track live status anytime in 'Orders' tab."
                )
            else:
                msg = (
                    f"🎉💳 <b>To'lovingiz muvaffaqiyatli qabul qilindi!</b>\n\n"
                    f"Buyurtma <b>#{order_id}</b> ({total_amount:,} so'm) to'landi va <b>Darxan Burger</b> oshxonasiga yetkazildi!\n\n"
                    f"👨‍🍳 Oshpazlarimiz sizning issiq va mazali buyurtmangizni tayyorlashga kirishishdi. "
                    f"Buyurtma holatini bot menyusida yoki Web App da kuzatishingiz mumkin! 🍔✨"
                )

            await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
    except Exception as e:
        log.warning(f"Mijozga to'lov tasdig'i xabarini yuborishda xato: {e}")

    log.info(f"✅ Buyurtma #{order_id} to'lovi tasdiqlandi va filial kanaliga yo'naltirildi.")
    return True

