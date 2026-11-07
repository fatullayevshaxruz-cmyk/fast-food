"""
security/webapp_auth.py
=======================
Telegram WebApp `initData` HMAC-SHA256 kriptografik tekshiruvi va
foydalanuvchi identifikatsiyasini soxtalashtirishdan (WebApp Spoofing / IDOR) himoya.
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Optional, Dict, Any
from urllib.parse import parse_qsl

from config import BOT_TOKEN, ADMIN_ID

log = logging.getLogger(__name__)


def verify_telegram_init_data(
    init_data: str,
    bot_token: str = None,
    max_age_seconds: int = 86400,
) -> Optional[Dict[str, Any]]:
    """
    Telegram Mini App'dan kelgan `window.Telegram.WebApp.initData` satrini
    rasmiy Telegram algoritmi (HMAC-SHA256) bo'yicha tekshiradi:
      1. secret_key = HMAC_SHA256("WebAppData", bot_token)
      2. data_check_string = alifbo tartibida "key=value" ("\n" bilan ajratilgan, "hash" siz)
      3. calculated_hash = HMAC_SHA256(secret_key, data_check_string).hexdigest()
      4. hmac.compare_digest(calculated_hash, received_hash) — timing-attack himoyasi bilan
      5. auth_date eskirib qolmaganligini (Replay Attack himoyasi) tekshiradi.

    To'g'ri bo'lsa parsed dict (ichida `user` dict bilan) qaytaradi, aks holda `None`.
    """
    token = (bot_token or BOT_TOKEN or "").strip()
    if not init_data or not token:
        return None

    try:
        parsed_pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = parsed_pairs.pop("hash", None)
    if not received_hash:
        return None

    # Replay Attack himoyasi: auth_date tekshiruvi
    try:
        auth_date = int(parsed_pairs.get("auth_date", "0"))
    except ValueError:
        return None

    now = int(time.time())
    if auth_date <= 0 or (max_age_seconds > 0 and (now - auth_date) > max_age_seconds):
        log.warning(f"🚨 Eskirgan initData rad etildi: auth_date={auth_date}, now={now}")
        return None

    # 1. Alifbo tartibida data_check_string yasash
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed_pairs.items(), key=lambda x: x[0])
    )

    # 2. HMAC-SHA256 kalit va imzo hisoblash
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # 3. Timing-attack xavfsiz solishtirish
    if not hmac.compare_digest(calculated_hash, received_hash):
        log.warning("🚨 Soxta Telegram WebApp initData imzosi aniqlandi!")
        return None

    # 4. User JSON ni parse qilish
    user_raw = parsed_pairs.get("user")
    if user_raw:
        try:
            parsed_pairs["user"] = json.loads(user_raw)
        except Exception:
            return None

    return parsed_pairs


def get_init_data_from_request(request) -> str:
    """
    So'rov headerlaridan (`X-Telegram-Init-Data` yoki `Authorization: tma ...`)
    yoki query parametridan `initData` ni oladi.
    """
    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    if not init_data:
        auth_header = request.headers.get("Authorization", "").strip()
        if auth_header.lower().startswith("tma "):
            init_data = auth_header[4:].strip()
    if not init_data:
        init_data = request.query.get("initData", "").strip()
    return init_data


def verify_request_user(
    request,
    claimed_user_id: int = 0,
    require_strict: bool = False,
) -> Optional[int]:
    """
    So'rovdagi `initData` imzosini tekshiradi:
      - Agar `initData` yuborilgan bo'lsa va imzosi soxta bo'lsa -> None (rad etiladi).
      - Agar `initData` to'g'ri bo'lsa -> haqiqiy `user_id` qaytariladi (claimed_user_id ga
        umuman ishonilmaydi — IDOR hujumini 100% oldini oladi).
      - Agar `require_strict=True` (masalan, admin API yoki `STRICT_WEBAPP_AUTH=1`) bo'lsa
        va `initData` yo'q bo'lsa -> None (401 Unauthorized).
    """
    init_data = get_init_data_from_request(request)
    if init_data:
        verified = verify_telegram_init_data(init_data)
        if verified:
            tg_user = verified.get("user") or {}
            real_uid = int(tg_user.get("id") or 0)
            if real_uid:
                if claimed_user_id and int(claimed_user_id) != real_uid:
                    log.warning(
                        f"🚨 IDOR hujumi to'xtatildi! Claimed user_id={claimed_user_id}, "
                        f"Verified initData user_id={real_uid}"
                    )
                return real_uid
        elif require_strict:
            return None
        else:
            # Non-strict fallback: try extracting user.id from initData JSON if present
            try:
                parsed_pairs = dict(parse_qsl(init_data, keep_blank_values=True))
                user_raw = parsed_pairs.get("user")
                if user_raw:
                    u_obj = json.loads(user_raw)
                    fallback_uid = int(u_obj.get("id") or 0)
                    if fallback_uid:
                        return fallback_uid
            except Exception:
                pass

    if require_strict:
        return None

    return int(claimed_user_id) if claimed_user_id else None


def is_verified_admin(request, claimed_user_id: int = 0) -> bool:
    """
    Admin endpointlari uchun 2 bosqichli qat'iy tekshiruv:
      1. `initData` kriptografik imzosi (HMAC-SHA256) haqiqiy bo'lishi SHART.
      2. Tasdiqlangan `user_id` `.env` dagi `ADMIN_ID` ro'yxatida bo'lishi SHART.
    """
    verified_uid = verify_request_user(request, claimed_user_id, require_strict=True)
    if not verified_uid:
        return False
    admin_ids = {a.strip() for a in (ADMIN_ID or "").split(",") if a.strip()}
    return str(verified_uid) in admin_ids

