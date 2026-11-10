"""
utils/order_cancel.py
=====================
Mijoz tomonidan buyurtmani bekor qilish (1 daqiqalik oyna).

Oqim:
  1. Buyurtma yaratilgach `send_customer_cancel_button()` chaqiriladi:
       → mijozga "❌ Buyurtmani bekor qilish" inline tugmali alohida xabar yuboriladi
       → CANCEL_WINDOW_SECONDS (60s) dan keyin bu xabar avtomatik O'CHIRILADI
         (mijozga umuman ko'rinmay qoladi).
  2. Mijoz tugmani bosadi → `customer_cancel_order_callback()`:
       → egasi, muddati va holati (faqat 'pending') tekshiriladi
       → bazada status = 'cancelled'
       → filial kanalidagi xabar "BEKOR QILINDI" ga o'zgartiriladi (tugmalarsiz)
       → mijozga tasdiq xabari.

Xavfsizlik:
  - Muddat server tomonida (in-memory) saqlanadi; bot qayta ishga tushsa,
    muddat yo'qoladi va bekor qilish rad etiladi (xavfsiz tomon).
  - Kafe allaqachon qabul qilgan (preparing/delivering/completed) yoki
    to'langan buyurtmani mijoz bekor qila olmaydi.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional

from aiogram import types, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger(__name__)

# Bekor qilish tugmasi necha soniya ko'rinadi
CANCEL_WINDOW_SECONDS = 60

_CB_PREFIX = "ucancel_"

# order_id -> {"user_id", "deadline", "chat_id", "message_id", "related": [message_id, ...]}
_CANCEL_WINDOWS: Dict[int, dict] = {}

# order_id -> {"chat_id", "message_id", "is_caption"}  (filial kanalidagi tasdiqlash xabari)
_CHANNEL_MESSAGES: Dict[int, dict] = {}
_CHANNEL_MSG_LIMIT = 2000


_TEXTS = {
    "prompt": {
        "uz": "⏳ Buyurtma <b>#{order_id}</b> ni <b>1 daqiqa</b> ichida bekor qilishingiz mumkin.",
        "ru": "⏳ Вы можете отменить заказ <b>#{order_id}</b> в течение <b>1 минуты</b>.",
        "en": "⏳ You can cancel order <b>#{order_id}</b> within <b>1 minute</b>.",
    },
    "button": {
        "uz": "❌ Buyurtmani bekor qilish",
        "ru": "❌ Отменить заказ",
        "en": "❌ Cancel order",
    },
    "cancelled": {
        "uz": "❌ Buyurtma <b>#{order_id}</b> bekor qilindi.",
        "ru": "❌ Заказ <b>#{order_id}</b> отменён.",
        "en": "❌ Order <b>#{order_id}</b> has been cancelled.",
    },
    "alert_cancelled": {
        "uz": "✅ Buyurtma bekor qilindi",
        "ru": "✅ Заказ отменён",
        "en": "✅ Order cancelled",
    },
    "expired": {
        "uz": "⌛ Bekor qilish vaqti tugagan (1 daqiqa).",
        "ru": "⌛ Время для отмены истекло (1 минута).",
        "en": "⌛ The cancellation window (1 minute) has expired.",
    },
    "already_accepted": {
        "uz": "ℹ️ Buyurtma allaqachon kafe tomonidan qabul qilingan, bekor qilib bo'lmaydi.",
        "ru": "ℹ️ Заказ уже принят кафе, отменить нельзя.",
        "en": "ℹ️ The order has already been accepted by the cafe and cannot be cancelled.",
    },
    "already_cancelled": {
        "uz": "ℹ️ Bu buyurtma allaqachon bekor qilingan.",
        "ru": "ℹ️ Этот заказ уже отменён.",
        "en": "ℹ️ This order is already cancelled.",
    },
    "already_paid": {
        "uz": "ℹ️ Buyurtma to'langan, bekor qilish uchun operatorga murojaat qiling.",
        "ru": "ℹ️ Заказ уже оплачен, для отмены обратитесь к оператору.",
        "en": "ℹ️ The order is already paid, please contact the operator to cancel.",
    },
    "not_found": {
        "uz": "⚠️ Buyurtma topilmadi.",
        "ru": "⚠️ Заказ не найден.",
        "en": "⚠️ Order not found.",
    },
}


def _t(key: str, lang: str, **kwargs) -> str:
    variants = _TEXTS.get(key, {})
    text = variants.get(lang) or variants.get("uz") or key
    return text.format(**kwargs) if kwargs else text


# ── Filial kanalidagi xabarni eslab qolish ────────────────────────────

def register_channel_message(order_id: int, message: Optional[types.Message]):
    """notify_admins_new_order tomonidan chaqiriladi (tasdiqlash tugmali xabar)."""
    if not message:
        return
    try:
        if len(_CHANNEL_MESSAGES) >= _CHANNEL_MSG_LIMIT:
            # Eng eskilarini tozalash
            for k in list(_CHANNEL_MESSAGES.keys())[: _CHANNEL_MSG_LIMIT // 2]:
                _CHANNEL_MESSAGES.pop(k, None)
        _CHANNEL_MESSAGES[int(order_id)] = {
            "chat_id": message.chat.id,
            "message_id": message.message_id,
            "is_caption": message.caption is not None,
            "html": message.html_text if (message.text or message.caption) else "",
        }
    except Exception as e:
        log.warning(f"register_channel_message xato: {e}")


# ── Mijozga tugma yuborish ────────────────────────────────────────────

async def send_customer_cancel_button(bot, user_id: int, order_id: int, lang: str = "uz",
                                      related_message_ids: Optional[List[int]] = None):
    """
    Mijozga bekor qilish tugmali xabar yuboradi va 1 daqiqadan keyin uni o'chiradi.
    related_message_ids — bekor qilinganda inline tugmalari olib tashlanadigan
    boshqa xabarlar (masalan, Payme/Click to'lov tugmalari).
    """
    if not bot:
        return
    try:
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton(_t("button", lang), callback_data=f"{_CB_PREFIX}{order_id}")
        )
        msg = await bot.send_message(
            chat_id=user_id,
            text=_t("prompt", lang, order_id=order_id),
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as e:
        log.warning(f"Bekor qilish tugmasini yuborishda xato (order #{order_id}): {e}")
        return

    _CANCEL_WINDOWS[int(order_id)] = {
        "user_id": int(user_id),
        "deadline": time.monotonic() + CANCEL_WINDOW_SECONDS,
        "chat_id": msg.chat.id,
        "message_id": msg.message_id,
        "related": list(related_message_ids or []),
    }
    asyncio.create_task(_expire_cancel_button(bot, int(order_id), msg.chat.id, msg.message_id))


async def _expire_cancel_button(bot, order_id: int, chat_id: int, message_id: int):
    await asyncio.sleep(CANCEL_WINDOW_SECONDS)
    window = _CANCEL_WINDOWS.get(order_id)
    # Agar mijoz allaqachon bekor qilgan bo'lsa, oyna o'chirilgan — xabarga tegmaymiz
    if not window or window.get("message_id") != message_id:
        return
    _CANCEL_WINDOWS.pop(order_id, None)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        # O'chirib bo'lmasa — hech bo'lmasa tugmani olib tashlaymiz
        try:
            await bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
        except Exception:
            pass


# ── Callback: mijoz tugmani bosdi ─────────────────────────────────────

async def customer_cancel_order_callback(call: types.CallbackQuery):
    from database.crud import get_order_by_id, update_order_status, get_user_language

    user_id = call.from_user.id
    lang = await get_user_language(user_id)

    try:
        order_id = int(call.data[len(_CB_PREFIX):])
    except Exception:
        await call.answer(_t("not_found", lang), show_alert=True)
        return

    window = _CANCEL_WINDOWS.get(order_id)
    if not window or window["user_id"] != user_id or time.monotonic() > window["deadline"]:
        if window and window["user_id"] == user_id:
            _CANCEL_WINDOWS.pop(order_id, None)
        await call.answer(_t("expired", lang), show_alert=True)
        try:
            await call.message.delete()
        except Exception:
            pass
        return

    order_row = await get_order_by_id(order_id)
    if not order_row:
        await call.answer(_t("not_found", lang), show_alert=True)
        return
    order = dict(order_row)

    if int(order.get("user_id") or 0) != user_id:
        await call.answer(_t("not_found", lang), show_alert=True)
        return

    status = order.get("status") or "pending"
    pay_status = str(order.get("payment_status") or "unpaid")
    is_online = "online" in str(order.get("payment_method") or "").lower()

    if status == "cancelled":
        _CANCEL_WINDOWS.pop(order_id, None)
        await call.answer(_t("already_cancelled", lang), show_alert=True)
        return
    if status != "pending":
        _CANCEL_WINDOWS.pop(order_id, None)
        await call.answer(_t("already_accepted", lang), show_alert=True)
        try:
            await call.message.delete()
        except Exception:
            pass
        return
    if is_online and pay_status == "paid":
        _CANCEL_WINDOWS.pop(order_id, None)
        await call.answer(_t("already_paid", lang), show_alert=True)
        return

    _CANCEL_WINDOWS.pop(order_id, None)
    await update_order_status(order_id, "cancelled")
    await call.answer(_t("alert_cancelled", lang), show_alert=False)
    log.info(f"❌ Buyurtma #{order_id} mijoz tomonidan bekor qilindi (user={user_id}).")

    # Mijoz xabarini yangilash (tugmasiz)
    try:
        await call.message.edit_text(_t("cancelled", lang, order_id=order_id),
                                     parse_mode="HTML", reply_markup=None)
    except Exception:
        pass

    # To'lov tugmalari kabi bog'liq xabarlardan tugmalarni olib tashlash
    for mid in window.get("related") or []:
        try:
            await call.bot.edit_message_reply_markup(window["chat_id"], mid, reply_markup=None)
        except Exception:
            pass

    await _mark_channel_message_cancelled(call.bot, order_id, order)


async def _mark_channel_message_cancelled(bot, order_id: int, order: dict):
    """Filial kanalidagi buyurtma xabarini 'mijoz bekor qildi' holatiga o'tkazadi."""
    status_line = "❌ <b>Holat: MIJOZ TOMONIDAN BEKOR QILINDI</b>"
    info = _CHANNEL_MESSAGES.pop(order_id, None)

    if info:
        html = info.get("html") or ""
        if "⏳ <i>Holat: Kafe tasdiqlashi kutilmoqda...</i>" in html:
            html = html.replace("⏳ <i>Holat: Kafe tasdiqlashi kutilmoqda...</i>", status_line)
        else:
            html = f"{html}\n\n{status_line}" if html else f"Buyurtma #{order_id}\n\n{status_line}"
        try:
            if info.get("is_caption"):
                await bot.edit_message_caption(info["chat_id"], info["message_id"],
                                               caption=html, parse_mode="HTML", reply_markup=None)
            else:
                await bot.edit_message_text(html, info["chat_id"], info["message_id"],
                                            parse_mode="HTML", reply_markup=None)
            return
        except Exception as e:
            log.warning(f"Kanal xabarini bekor qilingan deb yangilashda xato: {e}")
            try:
                await bot.edit_message_reply_markup(info["chat_id"], info["message_id"], reply_markup=None)
            except Exception:
                pass
            # Davomida alohida xabar ham yuboriladi
            try:
                await bot.send_message(info["chat_id"],
                                       f"❌ <b>Buyurtma #{order_id}</b> mijoz tomonidan bekor qilindi.",
                                       parse_mode="HTML", reply_to_message_id=info["message_id"])
            except Exception:
                pass
        return

    # Kanal xabari ma'lum emas: online (to'lanmagan) buyurtma kanalga hali yuborilmagan bo'ladi.
    is_online = "online" in str(order.get("payment_method") or "").lower()
    if is_online:
        return
    try:
        from config import ADMIN_CHANNEL_ID
        if ADMIN_CHANNEL_ID:
            await bot.send_message(ADMIN_CHANNEL_ID,
                                   f"❌ <b>Buyurtma #{order_id}</b> mijoz tomonidan bekor qilindi.",
                                   parse_mode="HTML")
    except Exception as e:
        log.warning(f"Bekor qilish haqida kanalga xabar yuborishda xato: {e}")


async def mark_if_already_cancelled(bot, order_id: int):
    """
    Poyga holati: mijoz kanal xabari yuborilishidan OLDIN bekor qilgan bo'lsa,
    endigina yuborilgan kanal xabarini darhol 'bekor qilindi' qilib qo'yamiz.
    """
    try:
        from database.crud import get_order_by_id
        row = await get_order_by_id(order_id)
        if row and (dict(row).get("status") == "cancelled"):
            await _mark_channel_message_cancelled(bot, int(order_id), dict(row))
    except Exception as e:
        log.warning(f"mark_if_already_cancelled xato: {e}")


def register_order_cancel_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(
        customer_cancel_order_callback,
        lambda c: c.data and c.data.startswith(_CB_PREFIX),
        state="*",
    )
