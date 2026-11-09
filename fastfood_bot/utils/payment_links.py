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
