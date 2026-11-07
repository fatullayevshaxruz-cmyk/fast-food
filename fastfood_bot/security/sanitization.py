"""
security/sanitization.py
========================
Barcha foydalanuvchi kiritmalari (manzil, izoh, telefon raqam, savat miqdori,
koordinatalar) uchun qat'iy validatsiya va HTML/XSS tozalash hamda
CSPRNG asosidagi xavfsiz OTP menejeri.
"""

import html
import re
import secrets
import time
from typing import Optional, Tuple, Dict, Any

MAX_ITEM_QUANTITY = 50       # Bitta mahsulotdan maksimal 50 dona (Integer Overflow himoyasi)
MAX_CART_DISTINCT_ITEMS = 30 # Savatda maksimal 30 xil mahsulot
OTP_TTL_SECONDS = 300        # OTP kod amal qilish muddati: 5 daqiqa
OTP_MAX_ATTEMPTS = 5         # Maksimal xato urinishlar soni (Brute-Force himoyasi)


def sanitize_text(value: Any, max_len: int = 300) -> str:
    """
    HTML teglarni escape qiladi (XSS va Telegram HTML parse_mode injection himoyasi)
    va nazorat belgilarini olib tashlaydi.
    """
    if value is None:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value).strip())
    return html.escape(cleaned[:max_len], quote=True)


def sanitize_phone(phone: Any) -> str:
    """Telefon raqamni xavfsiz formatga keltiradi (+998XXXXXXXXX)."""
    if not phone:
        return ""
    digits = re.sub(r"[^\d+]", "", str(phone).strip())
    return digits[:20]


def clamp_quantity(qty: Any) -> int:
    """
    Manfiy son (Negative Quantity Price Hack) yoki 2^31 Integer Overflow
    hujumlarining oldini oladi. Faqat [1..50] oralig'idagi butun son qaytaradi.
    """
    try:
        val = int(qty)
    except (ValueError, TypeError):
        return 1
    if val < 1:
        return 1
    if val > MAX_ITEM_QUANTITY:
        return MAX_ITEM_QUANTITY
    return val


def validate_coordinates(lat: Any, lon: Any) -> Tuple[Optional[float], Optional[float]]:
    """Geolokatsiya koordinatalarini haqiqiy Yer diapazonida ekanligini tekshiradi."""
    if lat is None or lon is None:
        return None, None
    try:
        la = float(lat)
        lo = float(lon)
        if -90.0 <= la <= 90.0 and -180.0 <= lo <= 180.0:
            return la, lo
    except (ValueError, TypeError):
        pass
    return None, None


class SecureOTPStore:
    """
    Kriptografik tasodifiy sonlar generatori (`secrets.randbelow`) yordamida
    6 xonali OTP yaratadi, 5 daqiqa amal qilish muddati va maksimal 5 ta urinish
    cheklovi (Brute-Force Lockout) bilan himoyalaydi.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def generate(self, key: str, phone: str, method: str) -> str:
        code = f"{secrets.randbelow(900000) + 100000}"
        record = {
            "code": code,
            "phone": phone,
            "method": method,
            "expires_at": time.monotonic() + OTP_TTL_SECONDS,
            "attempts": 0,
        }
        self._store[key] = record
        self._store[phone] = record
        return code

    def verify(self, key: str, phone: str, submitted_code: str) -> Tuple[bool, str]:
        import hmac
        record = self._store.get(key) or self._store.get(phone)
        if not record:
            return False, "Kod topilmadi yoki muddati tugagan. Yangi kod so'rang."

        if time.monotonic() > record["expires_at"]:
            self._store.pop(key, None)
            self._store.pop(phone, None)
            return False, "Kodning amal qilish muddati tugagan (5 daqiqa)."

        record["attempts"] += 1
        if record["attempts"] > OTP_MAX_ATTEMPTS:
            self._store.pop(key, None)
            self._store.pop(phone, None)
            return False, "Juda ko'p xato urinish! Xavfsizlik uchun kod bekor qilindi."

        if not hmac.compare_digest(str(record["code"]), str(submitted_code).strip()):
            remaining = OTP_MAX_ATTEMPTS - record["attempts"]
            return False, f"Noto'g'ri tasdiqlash kodi (qolgan urinishlar: {remaining})"

        # Muvaffaqiyatli tasdiqlangach darhol o'chiramiz (One-Time Use)
        self._store.pop(key, None)
        self._store.pop(phone, None)
        return True, "OK"


otp_store = SecureOTPStore()

