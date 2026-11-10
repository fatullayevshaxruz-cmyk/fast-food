"""
utils/payment_links.py
======================
Click va Payme ilovalari va to'lov sahifalariga to'g'ridan-to'g'ri kirish
(Deep Link / Checkout URL) generatorlari.

Foydalanuvchi taqdim etgan spetsifikatsiya:
1. Click:
   https://my.click.uz/services/pay?service_id={service_id}&merchant_id={merchant_id}&amount={amount}&transaction_param={order_id}

2. Payme:
   https://checkout.paycom.uz/{base64_encoded_params}
   params = "m={merchant_id};ac.order_id={order_id};a={tiyin_amount}"
"""

import base64
from typing import Optional, Dict
from config import CLICK_MERCHANT_ID, CLICK_SERVICE_ID, PAYME_MERCHANT_ID


def generate_click_link(
    order_id: int,
    amount: float,
    merchant_id: Optional[str] = None,
    service_id: Optional[str] = None,
) -> str:
    """
    Click ilovasi yoki veb-saytiga to'g'ridan-to'g'ri yo'naltiruvchi to'lov havolasi.
    amount - so'mdagi summa (masalan: 45000 yoki 45000.0)
    """
    m_id = str(merchant_id or CLICK_MERCHANT_ID or "").strip()
    s_id = str(service_id or CLICK_SERVICE_ID or "").strip()
    
    # Summani to'g'ri formatlash (butun son bo'lsa int, aks holda float)
    try:
        f_amt = float(amount)
        amount_val = int(f_amt) if f_amt.is_integer() else round(f_amt, 2)
    except Exception:
        amount_val = amount

    return (
        f"https://my.click.uz/services/pay"
        f"?service_id={s_id}&merchant_id={m_id}&amount={amount_val}&transaction_param={order_id}"
    )


def generate_payme_link(
    order_id: int,
    amount: float,
    merchant_id: Optional[str] = None,
) -> str:
    """
    Payme ilovasi yoki veb-saytiga to'g'ridan-to'g'ri yo'naltiruvchi to'lov havolasi.
    Payme tiyinda qabul qiladi, shuning uchun summani 100 ga ko'paytiramiz.
    """
    m_id = str(merchant_id or PAYME_MERCHANT_ID or "").strip()
    try:
        tiyin_amount = int(float(amount) * 100)
    except Exception:
        tiyin_amount = 0

    params = f"m={m_id};ac.order_id={order_id};a={tiyin_amount}"
    encoded_params = base64.b64encode(params.encode("utf-8")).decode("utf-8")
    return f"https://checkout.paycom.uz/{encoded_params}"


def get_order_payment_links(order_id: int, amount: float) -> Dict[str, str]:
    """Buyurtma uchun Click va Payme to'lov havolalarini qaytaradi."""
    return {
        "click": generate_click_link(order_id, amount),
        "payme": generate_payme_link(order_id, amount),
    }


# ── Sozlanganlik holati ───────────────────────────────────────────────

def is_payme_enabled() -> bool:
    from config import PAYME_ENABLED
    return bool(PAYME_ENABLED)


def is_click_enabled() -> bool:
    from config import CLICK_ENABLED
    return bool(CLICK_ENABLED)


def is_online_payment_available() -> bool:
    return is_payme_enabled() or is_click_enabled()


def is_payment_method_available(payment_method: str) -> bool:
    """
    Mijoz tanlagan to'lov usuli (matn) hozir qabul qilinadimi:
      - naqd → har doim True
      - 'click' → Click sozlangan bo'lsa
      - 'payme' → Payme sozlangan bo'lsa
      - umumiy 'online' → kamida bittasi sozlangan bo'lsa
    """
    low = str(payment_method or "").lower()
    want_click = "click" in low
    want_payme = "payme" in low
    if want_click:
        return is_click_enabled()
    if want_payme:
        return is_payme_enabled()
    if "online" in low:
        return is_online_payment_available()
    return True


def get_payment_config() -> Dict[str, bool]:
    """WebApp uchun: qaysi to'lov usullari ko'rsatilishi mumkin."""
    return {
        "cash": True,
        "payme": is_payme_enabled(),
        "click": is_click_enabled(),
    }


def build_pay_keyboard(order_id: int, amount: float, prefer: Optional[str] = None):
    """
    Faqat SOZLANGAN to'lov tizimlari uchun tugmalar bilan inline klaviatura.
    prefer='click' bo'lsa Click tugmasi birinchi turadi.
    Hech biri sozlanmagan bo'lsa None qaytaradi.
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = []
    if is_payme_enabled():
        buttons.append(("payme", InlineKeyboardButton(
            "💳 Payme ilovasida to'lash", url=generate_payme_link(order_id, amount))))
    if is_click_enabled():
        buttons.append(("click", InlineKeyboardButton(
            "🔹 Click ilovasida to'lash", url=generate_click_link(order_id, amount))))
    if not buttons:
        return None
    if prefer == "click":
        buttons.sort(key=lambda b: 0 if b[0] == "click" else 1)

    kb = InlineKeyboardMarkup(row_width=1)
    for _, btn in buttons:
        kb.add(btn)
    kb.add(InlineKeyboardButton("🔄 To'lovni tekshirish", callback_data=f"chk_pay_{order_id}"))
    return kb

