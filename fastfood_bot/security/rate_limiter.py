"""
security/rate_limiter.py
========================
DDoS, Spam, Brute-Force va Soxta Buyurtmalar (Kitchen Printer Flood) dan himoya:
  1. Redis + In-Memory Sliding Window Rate Limiter (HTTP API va Bot uchun)
  2. Duplicate Order Idempotency Guard (15 soniya ichida bir xil buyurtmani qayta yuborishni bloklash)
  3. Aiogram Bot Anti-Flood Middleware (/start, tugmalar va buyurtma spamiga qarshi)
"""

import collections
import hashlib
import json
import logging
import os
import time
from typing import Tuple, Optional
from aiohttp import web
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from aiogram import types

log = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    Yuqori tezlikdagi Sliding Window Rate Limiter.
    Agar REDIS_URL mavjud bo'lsa Redis orqali ishlaydi, aks holda
    xotirada (In-Memory deque) avtomatik ravishda xavfsiz ishlaydi.
    """

    def __init__(self):
        self._buckets = collections.defaultdict(collections.deque)
        self._blocked_until = {}  # {key: timestamp}
        self._last_cleanup = time.monotonic()
        self._redis = None
        self._redis_checked = False

    async def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        redis_url = os.getenv("REDIS_URL", "").strip()
        if not redis_url:
            return None
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            log.info("✅ Redis Rate Limiter ulandi.")
        except Exception as e:
            log.info(f"ℹ️ Redis topilmadi ({e}), In-Memory Sliding Window Rate Limiter ishlatilmoqda.")
            self._redis = None
        return self._redis

    def _cleanup(self, now: float):
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        expired_blocks = [k for k, ts in self._blocked_until.items() if ts <= now]
        for k in expired_blocks:
            self._blocked_until.pop(k, None)

        empty_keys = []
        for k, dq in self._buckets.items():
            while dq and now - dq[0] > 300:
                dq.popleft()
            if not dq:
                empty_keys.append(k)
        for k in empty_keys:
            self._buckets.pop(k, None)

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        block_duration: int = 0,
    ) -> Tuple[bool, int]:
        """
        Tekshiradi: `key` uchun `window_seconds` ichida `max_requests` tadan oshmaganmi?
        Qaytaradi: `(allowed: bool, retry_after_seconds: int)`
        """
        now_wall = time.time()
        redis_client = await self._get_redis()
        if redis_client:
            try:
                block_key = f"rl:block:{key}"
                ttl = await redis_client.ttl(block_key)
                if ttl and ttl > 0:
                    return False, int(ttl)

                bucket_key = f"rl:win:{key}:{ int(now_wall // window_seconds) }"
                count = await redis_client.incr(bucket_key)
                if count == 1:
                    await redis_client.expire(bucket_key, window_seconds)
                if count > max_requests:
                    retry = block_duration if block_duration > 0 else window_seconds
                    if block_duration > 0:
                        await redis_client.setex(block_key, block_duration, "1")
                    return False, retry
                return True, 0
            except Exception:
                pass

        # In-Memory Sliding Window
        now = time.monotonic()
        self._cleanup(now)

        if key in self._blocked_until:
            remaining = int(self._blocked_until[key] - now)
            if remaining > 0:
                return False, remaining
            self._blocked_until.pop(key, None)

        dq = self._buckets[key]
        while dq and (now - dq[0]) > window_seconds:
            dq.popleft()

        if len(dq) >= max_requests:
            retry_after = block_duration if block_duration > 0 else max(1, int(window_seconds - (now - dq[0])))
            if block_duration > 0:
                self._blocked_until[key] = now + block_duration
            return False, retry_after

        dq.append(now)
        return True, 0


rate_limiter = SlidingWindowRateLimiter()

# ── Duplicate Order Idempotency Guard ─────────────────────────────────
_RECENT_ORDER_HASHES = {}  # {order_fingerprint: timestamp}


def check_and_record_order_idempotency(user_id: int, items: list, delivery_type: str, address: str, ttl_seconds: int = 15) -> bool:
    """
    Bir xil foydalanuvchi 15 soniya ichida aynan bir xil savatni 2 marta yuborsa
    (double-click yoki replay script), ikkinchisini bloklaydi.
    True = ruxsat berildi, False = dublikat aniqlandi.
    """
    now = time.monotonic()
    expired = [k for k, ts in _RECENT_ORDER_HASHES.items() if now - ts > ttl_seconds]
    for k in expired:
        _RECENT_ORDER_HASHES.pop(k, None)

    canonical = json.dumps({
        "u": int(user_id),
        "i": sorted(
            [(int(x.get("product_id", 0)), int(x.get("quantity", 1))) for x in (items or [])],
            key=lambda t: t[0]
        ),
        "d": str(delivery_type),
        "a": str(address or "").strip(),
    }, sort_keys=True)
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    if fingerprint in _RECENT_ORDER_HASHES:
        return False

    _RECENT_ORDER_HASHES[fingerprint] = now
    return True


def get_client_ip(request: web.Request) -> str:
    """Cloudflare / Render / Nginx proxy orqasidagi haqiqiy IP manzilni aniqlash."""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    peername = request.transport.get_extra_info("peername") if request.transport else None
    if peername:
        return str(peername[0])
    return request.remote or "unknown"


# ── HTTP Security Headers + Rate Limit Middleware (aiohttp) ───────────
MAX_REQUEST_BODY_BYTES = 256 * 1024  # 256 KB — DoS payload himoyasi


@web.middleware
async def security_and_rate_limit_middleware(request: web.Request, handler):
    # 1. Payload hajmini tekshirish (Memory Exhaustion DoS himoyasi)
    if request.content_length and request.content_length > MAX_REQUEST_BODY_BYTES:
        return web.json_response(
            {"error": "Payload Too Large (max 256 KB)"},
            status=413,
            headers={"Access-Control-Allow-Origin": "*"},
        )

    client_ip = get_client_ip(request)
    path = request.path

    # 2. Endpointga qarab Rate Limit qoidalari
    if request.method != "OPTIONS" and path.startswith("/api/"):
        if path == "/api/order/create":
            # Oshxona printeriga soxta cheklar ketmasligi uchun: max 3 ta buyurtma / 60 soniya
            allowed, retry = await rate_limiter.is_allowed(
                f"http:order:{client_ip}", max_requests=3, window_seconds=60, block_duration=60
            )
        elif path == "/api/auth/send-otp":
            # SMS / Telegram OTP flood himoyasi: max 3 ta kod / 60 soniya
            allowed, retry = await rate_limiter.is_allowed(
                f"http:send_otp:{client_ip}", max_requests=3, window_seconds=60, block_duration=120
            )
        elif path == "/api/auth/verify-otp":
            # OTP Brute-Force himoyasi: max 5 ta urinish / 60 soniya
            allowed, retry = await rate_limiter.is_allowed(
                f"http:verify_otp:{client_ip}", max_requests=5, window_seconds=60, block_duration=180
            )
        elif path.startswith("/api/admin/"):
            # Admin API himoyasi: max 20 ta so'rov / 10 soniya
            allowed, retry = await rate_limiter.is_allowed(
                f"http:admin:{client_ip}", max_requests=20, window_seconds=10, block_duration=30
            )
        else:
            # Umumiy API: max 35 ta so'rov / 10 soniya
            allowed, retry = await rate_limiter.is_allowed(
                f"http:api:{client_ip}", max_requests=35, window_seconds=10, block_duration=15
            )

        if not allowed:
            log.warning(f"🚨 HTTP 429 Rate Limit: ip={client_ip}, path={path}, retry_after={retry}s")
            return web.json_response(
                {
                    "error": f"Juda ko'p so'rov yuborildi! Iltimos, {retry} soniyadan keyin qayta urinib ko'ring.",
                    "retry_after": retry,
                },
                status=429,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Retry-After": str(retry),
                },
            )

    response = await handler(request)

    # 3. Xavfsizlik HTTP Headerlarini qo'shish (XSS, Clickjacking, MIME sniffing himoyasi)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    if path.startswith("/webapp/") or path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    if request.path.startswith("/webapp"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response


# ── Aiogram Bot Anti-Spam / Anti-Flood Middleware ─────────────────────
class BotAntiFloodMiddleware(BaseMiddleware):
    """
    Telegram botning o'ziga keladigan /start spam, tugma bosish spami va
    WebApp sendData flood hujumlarini avtomatik bloklaydi.
    """

    def __init__(self):
        super().__init__()
        self._notified_users = {}  # {user_id: timestamp}

    async def on_pre_process_message(self, message: types.Message, data: dict):
        if not message.from_user:
            return

        # To'lov xabarlarini (successful_payment) hech qachon bloklamaymiz!
        if message.content_type == types.ContentTypes.SUCCESSFUL_PAYMENT:
            return

        uid = message.from_user.id
        text = (message.text or "").strip()

        # 1. /start komandasi spami: 15 soniyada max 4 marta
        if text.startswith("/start"):
            allowed, retry = await rate_limiter.is_allowed(
                f"bot:start:{uid}", max_requests=4, window_seconds=15, block_duration=20
            )
            if not allowed:
                await self._warn_once(message, uid, retry)
                raise CancelHandler()

        # 2. WebApp sendData buyurtma spami: 60 soniyada max 3 ta buyurtma
        if message.web_app_data:
            allowed, retry = await rate_limiter.is_allowed(
                f"bot:webapp_order:{uid}", max_requests=3, window_seconds=60, block_duration=60
            )
            if not allowed:
                await self._warn_once(message, uid, retry)
                raise CancelHandler()

        # 3. Umumiy xabar flood: 3 soniyada max 6 ta xabar
        allowed, retry = await rate_limiter.is_allowed(
            f"bot:msg:{uid}", max_requests=6, window_seconds=3, block_duration=10
        )
        if not allowed:
            await self._warn_once(message, uid, retry)
            raise CancelHandler()

    async def on_pre_process_callback_query(self, call: types.CallbackQuery, data: dict):
        if not call.from_user:
            return
        uid = call.from_user.id
        allowed, retry = await rate_limiter.is_allowed(
            f"bot:cb:{uid}", max_requests=8, window_seconds=3, block_duration=8
        )
        if not allowed:
            try:
                await call.answer(
                    f"⏳ Iltimos, shoshilmang! {retry} soniya kuting.",
                    show_alert=True,
                )
            except Exception:
                pass
            raise CancelHandler()

    async def _warn_once(self, message: types.Message, uid: int, retry: int):
        now = time.monotonic()
        last_warn = self._notified_users.get(uid, 0)
        if now - last_warn > 10:
            self._notified_users[uid] = now
            try:
                await message.answer(
                    f"🛡 <b>Anti-Spam himoyasi:</b> Juda ko'p so'rov yubordingiz. "
                    f"Iltimos, <b>{retry} soniya</b> kuting.",
                    parse_mode="HTML",
                )
            except Exception:
                pass

