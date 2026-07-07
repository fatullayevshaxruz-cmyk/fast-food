"""
handlers/order_tracking.py
===========================
Buyurtma holati o'zgarganda foydalanuvchiga
chiroyli progress xabar yuborish.

Admin `admin_change_order_status()` dan chaqiriladi.
Mavjud kod o'zgarishsiz qoladi — bu faqat xabar formati.
"""

import asyncio
import logging
from aiogram import Bot
from utils.i18n import get_text

log = logging.getLogger(__name__)

# Her holat uchun: (qadam raqami, emoji)
_STATUS_META: dict = {
    "pending":    (1, "⏳"),
    "preparing":  (2, "🍳"),
    "delivering": (3, "🛵"),
    "completed":  (4, "✅"),
    "cancelled":  (0, "❌"),
}

# Progress chizig'idagi qadamlar
_STEPS = [
    (1, "⏳"),
    (2, "🍳"),
    (3, "🛵"),
    (4, "✅"),
]


def _build_progress_bar(status: str) -> str:
    """
    Chiroyli progress chizig'i misol:
      ✅ ➜ ▶️🍳 ➜ ⬜ ➜ ⬜
    """
    if status == "cancelled":
        return "❌ — — — — — —"

    step_num, _ = _STATUS_META.get(status, (0, "❓"))
    parts = []
    for num, emoji in _STEPS:
        if num < step_num:
            parts.append("✅")
        elif num == step_num:
            parts.append(f"▶️{emoji}")
        else:
            parts.append("⬜")
    return "  ➜  ".join(parts)


async def send_order_status_update(
    bot: Bot,
    user_id: int,
    order_id: int,
    new_status: str,
    lang: str,
    delivery_type: str = "delivery",
    courier_phone: str = None,
):
    """
    Buyurtma holati o'zgarganda foydalanuvchiga
    chiroyli, progress ko'rsatuvchi xabar yuboradi.

    Args:
        bot           — aiogram Bot obyekti
        user_id       — Telegram foydalanuvchi ID
        order_id      — Buyurtma raqami
        new_status    — Yangi holat: pending/preparing/delivering/completed/cancelled
        lang          — Foydalanuvchi tili: uz/ru/en
        delivery_type — delivery | eat_in
        courier_phone — Kuryer telefoni (faqat "delivering" holat uchun)
    """
    try:
        progress_bar = _build_progress_bar(new_status)

        # eat_in uchun alohida kalit
        if delivery_type == "eat_in" and new_status in ("delivering", "completed"):
            key_suffix = "_eat_in"
        else:
            key_suffix = ""

        msg_key = f"tracking_{new_status}{key_suffix}"
        msg = get_text(msg_key, lang, id=order_id, progress=progress_bar)

        # "Yetkazilmoqda" holatida kuryer raqami qo'shiladi
        if new_status == "delivering" and courier_phone:
            msg += (
                f"\n\n📞 <b>{get_text('tracking_courier_phone', lang)}</b>\n"
                f"<code>{courier_phone}</code>"
            )

        await bot.send_message(user_id, msg, parse_mode="HTML")

    except Exception as e:
        log.error(f"Status xabar yuborishda xatolik: {e}")
