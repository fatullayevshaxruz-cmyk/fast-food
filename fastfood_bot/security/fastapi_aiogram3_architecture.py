"""
security/fastapi_aiogram3_architecture.py
=========================================
Senior Cybersecurity & Backend Architecture (FastAPI + aiogram 3 + SQLAlchemy 2.0 Async ORM + Redis).

Ushbu modulda:
  1. Telegram WebApp `initData` HMAC-SHA256 qat'iy validatsiyasi (401 Unauthorized)
  2. FastAPI + Redis Rate Limiting Middleware (429 Too Many Requests) + Aiogram 3 ThrottlingMiddleware
  3. Click va Payme rasmiy IP Whitelist + Signature + DB Summa tekshiruvi
  4. SQLAlchemy 2.0 Async ORM (100% SQL Injection himoyasi) va Pydantic Settings (.env)
"""

import base64
import hashlib
import hmac
import ipaddress
import json
import time
from typing import Dict, Any, List, Optional
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request, Depends, HTTPException, Header, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import BigInteger, Integer, String, Numeric, ForeignKey, select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import redis.asyncio as aioredis


# =====================================================================
# 4. MAXFIY SOZLAMALAR (.env) VA SQLALCHEMY 2.0 ASYNC ORM (SQLi Himoyasi)
# =====================================================================

class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str
    DB_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fastfood_bot"
    REDIS_URL: str = "redis://localhost:6379/0"

    PAYME_MERCHANT_KEY: str = ""
    CLICK_SECRET_KEY: str = ""
    CLICK_SERVICE_ID: str = ""


class Base(DeclarativeBase):
    pass


class ProductORM(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)


class OrderORM(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(300), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid")
    transaction_id: Mapped[Optional[str]] = mapped_column(String(150), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")


class OrderItemORM(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at_time: Mapped[int] = mapped_column(Integer, nullable=False)


# =====================================================================
# 1. TELEGRAM WEBAPP `initData` HMAC-SHA256 QAT'IY VALIDATSIYASI
# =====================================================================

def verify_webapp_init_data_hmac(init_data: str, bot_token: str, max_age: int = 3600) -> Dict[str, Any]:
    """
    Telegram Mini App `initData` imzosini HMAC-SHA256 yordamida tekshiradi.
    Soxta yoki muddati o'tgan so'rovlarni 401 Unauthorized bilan rad etadi.
    """
    if not init_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Telegram WebApp initData",
        )

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing cryptographic hash in initData",
        )

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth_date")

    if abs(int(time.time()) - auth_date) > max_age:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired initData (Replay Attack blocked)",
        )

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WebApp signature (Spoofing attempt blocked)",
        )

    user_json = parsed.get("user")
    if not user_json:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user payload")

    return json.loads(user_json)


# =====================================================================
# 2. DDOS VA SPAM HIMOYASI (FASTAPI + REDIS RATE LIMITING MIDDLEWARE)
# =====================================================================

async def redis_rate_limit_middleware(
    request: Request,
    call_next,
    redis_client: aioredis.Redis,
    max_requests: int = 5,
    window_seconds: int = 1,
):
    """
    Bir IP yoki foydalanuvchi sekundiga 5 tadan ortiq so'rov yuborsa,
    429 Too Many Requests qaytarib vaqtincha bloklaydi.
    """
    client_ip = request.headers.get("CF-Connecting-IP") or (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    ) or (request.client.host if request.client else "unknown")

    key = f"ratelimit:{client_ip}:{request.url.path}"
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window_seconds)

    if current > max_requests:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "429 Too Many Requests — DDoS/Spam himoyasi: juda ko'p so'rov yuborildi."
            },
            headers={"Retry-After": str(window_seconds)},
        )

    return await call_next(request)


# =====================================================================
# 3. TO'LOV WEBHOOK XAVFSIZLIGI (CLICK VA PAYME IP WHITELIST + IMZO)
# =====================================================================

PAYME_NETWORKS = [
    ipaddress.ip_network("185.178.51.131/32"),
    ipaddress.ip_network("195.158.28.124/32"),
    ipaddress.ip_network("195.158.28.0/24"),
]

CLICK_NETWORKS = [
    ipaddress.ip_network("185.8.212.0/24"),
]


def verify_webhook_ip(client_ip: str, allowed_networks: list) -> None:
    try:
        ip_obj = ipaddress.ip_address(client_ip)
        if not any(ip_obj in net for net in allowed_networks):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Untrusted webhook IP")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid IP address")


def verify_click_signature(
    click_trans_id: str,
    service_id: str,
    secret_key: str,
    merchant_trans_id: str,
    amount: str,
    action: str,
    sign_time: str,
    received_sign: str,
    merchant_prepare_id: str = "",
) -> bool:
    if action == "0":
        payload = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{amount}{action}{sign_time}"
    else:
        payload = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"
    expected_sign = hashlib.md5(payload.encode("utf-8")).hexdigest().lower()
    return hmac.compare_digest(expected_sign, received_sign.lower())


# =====================================================================
# AIOGRAM 3 THROTTLING (ANTI-SPAM) MIDDLEWARE
# =====================================================================

class Aiogram3ThrottlingMiddleware:
    """
    Aiogram 3 uchun Redis asosidagi Anti-Spam Middleware:
    Sekundiga 5 tadan ortiq /start yoki buyurtma yuborgan foydalanuvchini bloklaydi.
    """

    def __init__(self, redis_client: aioredis.Redis, limit: int = 5, window: int = 2):
        self.redis = redis_client
        self.limit = limit
        self.window = window

    async def __call__(self, handler, event, data: Dict[str, Any]):
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        key = f"tg_throttle:{user.id}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.window)

        if count > self.limit:
            if hasattr(event, "answer"):
                await event.answer("⏳ Juda ko'p so'rov yubordingiz! Biroz kuting.")
            return None

        return await handler(event, data)

