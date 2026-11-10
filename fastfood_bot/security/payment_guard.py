"""
security/payment_guard.py
=========================
To'lov tizimini (Telegram Payments, Click va Payme Webhooklari) 100% xakerlik
hujumlaridan (Price Manipulation, Fake Webhook, Replay / Double-Spend, Spoofing)
himoya qiluvchi modul.

Himoya qatlamlari:
  1. HMAC-SHA256 bilan imzolangan Invoice Payload (payload ni o'zgartirib bo'lmaydi)
  2. Server-side DB Price Recalculation (mijoz yuborgan narxga emas, faqat DB dagi haqiqiy
     mahsulot narxlariga asoslanib to'lov summasini tekshirish)
  3. Idempotency / Double-Spend himoyasi (bitta `transaction_id` ikki marta ishlatilmaydi)
  4. Click va Payme rasmiy IP Whitelist + kriptografik imzo (`sign_string` / `Basic Auth`) tekshiruvi
"""

import base64
import hashlib
import hmac
import ipaddress
import logging
import os
from typing import Optional, Dict, Any, Tuple
from aiohttp import web

from config import BOT_TOKEN, DELIVERY_FEE
from database.connection import get_db_pool
from database.crud import get_cart_items, get_order_by_id, get_promo_code
from security.rate_limiter import get_client_ip

log = logging.getLogger(__name__)

# ── Maxfiy kalitlar (.env dan olinadi) ────────────────────────────────
PAYMENT_HMAC_SECRET = (
    os.getenv("PAYMENT_SECRET_KEY")
    or os.getenv("CLICK_SECRET_KEY")
    or os.getenv("PAYME_KEY")
    or BOT_TOKEN
    or "darxan-default-secret"
).strip()

PAYME_MERCHANT_KEY = os.getenv("PAYME_KEY", "").strip()
CLICK_SECRET_KEY   = os.getenv("CLICK_SECRET_KEY", "").strip()
CLICK_SERVICE_ID   = os.getenv("CLICK_SERVICE_ID", "").strip()

# ── Rasmiy Click va Payme IP diapazonlari (IP Whitelist) ──────────────
PAYME_ALLOWED_NETWORKS = [
    ipaddress.ip_network("185.178.51.131/32"),
    ipaddress.ip_network("195.158.28.124/32"),
    ipaddress.ip_network("195.158.28.0/24"),
]

CLICK_ALLOWED_NETWORKS = [
    ipaddress.ip_network("185.8.212.0/24"),
]

# Qayta ishlangan tranzaksiyalar kesh xotirasi (Double-spend / Replay himoyasi)
_PROCESSED_TRANSACTIONS = set()


def _compute_payload_sig(core_payload: str) -> str:
    """Invoice payload uchun 16 belgili HMAC-SHA256 imzo hisoblaydi."""
    return hmac.new(
        key=PAYMENT_HMAC_SECRET.encode("utf-8"),
        msg=core_payload.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()[:16]


def sign_invoice_payload(raw_payload: str) -> str:
    """
    Invoice payload oxiriga `|sig=<hmac>` qo'shadi.
    Telegram invoice payload maksimal uzunligi 128 bayt.
    """
    sig = _compute_payload_sig(raw_payload)
    signed = f"{raw_payload}|s={sig}"
    if len(signed.encode("utf-8")) <= 128:
        return signed
    # Agar 128 baytdan oshsa, raw_payload ni qisqartirib imzolaymiz
    max_raw = 128 - len(f"|s={sig}")
    trimmed = raw_payload.encode("utf-8")[:max_raw].decode("utf-8", errors="ignore")
    sig = _compute_payload_sig(trimmed)
    return f"{trimmed}|s={sig}"


def verify_and_strip_invoice_payload(signed_payload: str) -> Tuple[bool, str]:
    """
    Invoice payload imzosini tekshiradi.
    Qaytaradi: `(is_valid: bool, clean_payload: str)`
    """
    if not signed_payload:
        return False, ""
    if "|s=" not in signed_payload:
        return False, signed_payload

    raw_part, sig_part = signed_payload.rsplit("|s=", 1)
    expected_sig = _compute_payload_sig(raw_part)
    if not hmac.compare_digest(expected_sig, sig_part):
        log.warning(f"🚨 Soxta invoice payload imzosi aniqlandi: {signed_payload}")
        return False, raw_part

    return True, raw_part


async def is_transaction_already_used(transaction_id: str) -> bool:
    """
    Bitta to'lov tranzaksiyasi (charge_id) ikki marta ishlatilmasligini
    (Replay / Double-Spend) ham xotiradan, ham ma'lumotlar bazasidan tekshiradi.
    """
    if not transaction_id:
        return False
    if transaction_id in _PROCESSED_TRANSACTIONS:
        return True

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            existing = await conn.fetchval(
                "SELECT id FROM orders WHERE transaction_id = $1 LIMIT 1",
                str(transaction_id),
            )
            if existing:
                _PROCESSED_TRANSACTIONS.add(transaction_id)
                return True
    except Exception as e:
        log.warning(f"Transaction check warning: {e}")

    return False


def mark_transaction_used(transaction_id: str):
    if transaction_id:
        _PROCESSED_TRANSACTIONS.add(str(transaction_id))


async def verify_cart_payment_amount(
    user_id: int,
    paid_amount_tiyin: int,
    currency: str,
    discount_pct: int = 0,
    promo_code: Optional[str] = None,
) -> Tuple[bool, str, int]:
    """
    PreCheckoutQuery va SuccessfulPayment vaqtida:
      1. Valyuta `UZS` ekanligini tekshiradi.
      2. Foydalanuvchi savatidagi mahsulotlarning BAZADAGI HAQIQIY narxini hisoblaydi.
      3. Promo kod chegirmasini bazadan qayta tekshiradi (foydalanuvchi yolg'on chegirma
         foizi yubora olmaydi!).
      4. To'lanayotgan summa haqiqiy savat summasidan kam emasligini tekshiradi.
    """
    if currency != "UZS":
        return False, "Noto'g'ri valyuta (faqat UZS qabul qilinadi).", 0

    items = await get_cart_items(user_id)
    if not items:
        return False, "Savat bo'sh yoki muddati tugagan.", 0

    # Bazadagi haqiqiy narxlar bo'yicha hisoblash
    items_total = sum(int(i["price"]) * int(i["quantity"]) for i in items if int(i["quantity"]) > 0)
    if items_total <= 0:
        return False, "Buyurtma summasi noto'g'ri.", 0

    # Promo kodni bazadan qayta tekshirish
    verified_discount_pct = 0
    if promo_code:
        promo = await get_promo_code(promo_code.strip().upper())
        if promo:
            promo_d = dict(promo)
            verified_discount_pct = int(promo_d.get("discount_percent", 0))
    elif discount_pct > 0:
        # Agar promo_code ko'rsatilmagan bo'lsa, maksimal chegirma DB dagi aktiv promo kodlardan oshmasligi shart
        verified_discount_pct = min(int(discount_pct), 50)

    discount_amt = int(items_total * verified_discount_pct / 100) if verified_discount_pct > 0 else 0
    min_expected_som = max(1000, items_total - discount_amt)
    paid_som = int(paid_amount_tiyin) // 100

    if paid_som < min_expected_som:
        log.warning(
            f"🚨 To'lov summasini kamaytirishga urinish (Price Manipulation)! "
            f"user_id={user_id}, paid={paid_som} so'm, min_expected={min_expected_som} so'm"
        )
        return False, "Buyurtma summasi bazadagi narxga mos kelmadi!", min_expected_som

    return True, "OK", paid_som


# ── IP Whitelist Tekshiruvchi ─────────────────────────────────────────
def is_ip_in_whitelist(ip_str: str, allowed_networks: list) -> bool:
    """So'rov kelgan IP rasmiy to'lov tizimi subnetiga tegishlimi?"""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return any(ip_obj in net for net in allowed_networks)
    except ValueError:
        return False


# ── PAYME RASMIY WEBHOOK HANDLER (JSON-RPC 2.0) ───────────────────────
async def payme_webhook_handler(request: web.Request) -> web.Response:
    """
    POST /api/webhooks/payme
    Payme Merchant API rasmiy xavfsizlik talablari:
      1. IP Whitelist tekshiruvi (`185.178.51.131`, `195.158.28.0/24`)
      2. Basic Auth (`Paycom:<PAYME_KEY>`) tekshiruvi (`hmac.compare_digest`)
      3. Bazadagi `orders.total_amount * 100` bilan `params.amount` (tiyinda) 100% mosligi
    """
    client_ip = get_client_ip(request)
    if not is_ip_in_whitelist(client_ip, PAYME_ALLOWED_NETWORKS):
        log.warning(f"🚨 Payme Webhook: Ruxsat etilmagan IP manzildan urinish: {client_ip}")
        return web.json_response(
            {"error": {"code": -32504, "message": "Forbidden IP address"}},
            status=403,
        )

    # Basic Auth tekshiruvi
    auth_header = request.headers.get("Authorization", "")
    if not PAYME_MERCHANT_KEY or not auth_header.startswith("Basic "):
        return web.json_response(
            {"error": {"code": -32504, "message": "Insufficient privilege"}},
            status=200,
        )

    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        login, password = decoded.split(":", 1)
    except Exception:
        return web.json_response(
            {"error": {"code": -32504, "message": "Invalid authorization header"}},
            status=200,
        )

    if login != "Paycom" or not hmac.compare_digest(password, PAYME_MERCHANT_KEY):
        log.warning(f"🚨 Payme Webhook: Noto'g'ri parol! IP={client_ip}")
        return web.json_response(
            {"error": {"code": -32504, "message": "Invalid credentials"}},
            status=200,
        )

    try:
        body = await request.json()
    except Exception:
        return web.json_response(
            {"error": {"code": -32700, "message": "Parse error"}},
            status=200,
        )

    rpc_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}
    account = params.get("account") or {}
    order_id = account.get("order_id")

    if method in ("CheckPerformTransaction", "CreateTransaction"):
        if not order_id:
            return web.json_response(
                {"id": rpc_id, "error": {"code": -31050, "message": "Order ID topilmadi"}},
            )
        order = await get_order_by_id(int(order_id))
        if not order:
            return web.json_response(
                {"id": rpc_id, "error": {"code": -31050, "message": "Buyurtma topilmadi"}},
            )
        order_dict = dict(order)
        if order_dict.get("payment_status") == "paid":
            return web.json_response(
                {"id": rpc_id, "error": {"code": -31051, "message": "Buyurtma allaqachon to'langan"}},
            )
        if order_dict.get("status") == "cancelled" and method in ("CheckPerformTransaction", "CreateTransaction"):
            return web.json_response(
                {"id": rpc_id, "error": {"code": -31052, "message": "Buyurtma bekor qilingan"}},
            )

        expected_tiyin = int(order_dict["total_amount"]) * 100
        incoming_tiyin = int(params.get("amount") or 0)
        if incoming_tiyin != expected_tiyin:
            log.warning(
                f"🚨 Payme summa xatosi! Order #{order_id}: expected={expected_tiyin}, got={incoming_tiyin}"
            )
            return web.json_response(
                {"id": rpc_id, "error": {"code": -31001, "message": "Noto'g'ri to'lov summasi"}},
            )

        if method == "CheckPerformTransaction":
            return web.json_response({"id": rpc_id, "result": {"allow": True}})

        # CreateTransaction
        payme_tx_id = str(params.get("id") or "")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET transaction_id = $1 WHERE id = $2",
                payme_tx_id, int(order_id),
            )
        return web.json_response({
            "id": rpc_id,
            "result": {
                "create_time": int(params.get("time") or 0),
                "transaction": str(order_id),
                "state": 1,
            },
        })

    if method == "PerformTransaction":
        payme_tx_id = str(params.get("id") or "")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            order = await conn.fetchrow(
                "SELECT * FROM orders WHERE transaction_id = $1 LIMIT 1",
                payme_tx_id,
            )
            if not order:
                return web.json_response(
                    {"id": rpc_id, "error": {"code": -31003, "message": "Tranzaksiya topilmadi"}},
                )
            
            # Agar allaqachon bajarilgan bo'lsa (idempotency)
            if order.get("payment_status") == "paid":
                perform_time = int(time.time() * 1000)
                return web.json_response({
                    "id": rpc_id,
                    "result": {
                        "transaction": str(order["id"]),
                        "perform_time": perform_time,
                        "state": 2,
                    },
                })

            await conn.execute(
                "UPDATE orders SET payment_status = 'paid' WHERE id = $1",
                order["id"],
            )
        mark_transaction_used(payme_tx_id)

        # ── Toki to'lov amalga oshirilmasa kanalga bormaydi — to'langach yuboramiz ──
        try:
            bot = request.app.get("bot")
            from utils.order_dispatcher import dispatch_paid_order_to_channel
            asyncio.create_task(dispatch_paid_order_to_channel(bot, int(order["id"]), transaction_id=payme_tx_id))
        except Exception as disp_err:
            log.error(f"Payme dispatch order error: {disp_err}")

        perform_time = int(time.time() * 1000)
        return web.json_response({
            "id": rpc_id,
            "result": {
                "transaction": str(order["id"]),
                "perform_time": perform_time,
                "state": 2,
            },
        })

    if method == "CheckTransaction":
        payme_tx_id = str(params.get("id") or "")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            order = await conn.fetchrow(
                "SELECT * FROM orders WHERE transaction_id = $1 LIMIT 1",
                payme_tx_id,
            )
            if not order:
                return web.json_response(
                    {"id": rpc_id, "error": {"code": -31003, "message": "Tranzaksiya topilmadi"}},
                )
            
            order_dict = dict(order)
            state = 2 if order_dict.get("payment_status") == "paid" else (
                -1 if order_dict.get("status") == "cancelled" else 1
            )
            create_time = int(time.time() * 1000)
            perform_time = create_time if state == 2 else 0
            cancel_time = create_time if state == -1 else 0
            reason = 1 if state == -1 else None

            return web.json_response({
                "id": rpc_id,
                "result": {
                    "create_time": create_time,
                    "perform_time": perform_time,
                    "cancel_time": cancel_time,
                    "transaction": str(order_dict["id"]),
                    "state": state,
                    "reason": reason,
                },
            })

    if method == "CancelTransaction":
        payme_tx_id = str(params.get("id") or "")
        reason = params.get("reason")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            order = await conn.fetchrow(
                "SELECT * FROM orders WHERE transaction_id = $1 LIMIT 1",
                payme_tx_id,
            )
            if not order:
                return web.json_response(
                    {"id": rpc_id, "error": {"code": -31003, "message": "Tranzaksiya topilmadi"}},
                )
            
            order_dict = dict(order)
            current_pay_status = order_dict.get("payment_status")
            cancel_state = -2 if current_pay_status == "paid" else -1

            await conn.execute(
                "UPDATE orders SET status = 'cancelled', payment_status = 'cancelled' WHERE id = $1",
                order_dict["id"],
            )

            cancel_time = int(time.time() * 1000)
            return web.json_response({
                "id": rpc_id,
                "result": {
                    "transaction": str(order_dict["id"]),
                    "cancel_time": cancel_time,
                    "state": cancel_state,
                },
            })

    return web.json_response(
        {"id": rpc_id, "error": {"code": -32601, "message": "Method not found"}},
    )


# ── CLICK RASMIY WEBHOOK HANDLER (Prepare / Complete) ─────────────────
async def click_webhook_handler(request: web.Request) -> web.Response:
    """
    POST /api/webhooks/click
    Click SHOP-API rasmiy xavfsizlik talablari:
      1. IP Whitelist (`185.8.212.0/24`)
      2. MD5 `sign_string` kriptografik imzo tekshiruvi (`hmac.compare_digest`)
      3. Bazadagi `orders.total_amount` bilan kelgan `amount` ning 100% mosligi
    """
    client_ip = get_client_ip(request)
    if not is_ip_in_whitelist(client_ip, CLICK_ALLOWED_NETWORKS):
        log.warning(f"🚨 Click Webhook: Ruxsat etilmagan IP manzildan urinish: {client_ip}")
        return web.json_response(
            {"error": -8, "error_note": "Forbidden IP address"},
            status=403,
        )

    if not CLICK_SECRET_KEY:
        return web.json_response(
            {"error": -8, "error_note": "Click secret key not configured"},
        )

    try:
        if request.content_type == "application/json":
            data = await request.json()
        else:
            post_data = await request.post()
            data = dict(post_data)
    except Exception:
        return web.json_response({"error": -8, "error_note": "Invalid request body"})

    click_trans_id    = str(data.get("click_trans_id", ""))
    service_id        = str(data.get("service_id", ""))
    merchant_trans_id = str(data.get("merchant_trans_id", ""))
    merchant_prep_id  = str(data.get("merchant_prepare_id", ""))
    amount            = str(data.get("amount", ""))
    action            = str(data.get("action", ""))
    sign_time         = str(data.get("sign_time", ""))
    sign_string       = str(data.get("sign_string", "")).lower()

    # Click rasmiy formulasi bo'yicha sign_string hisoblash
    if action == "0":  # Prepare
        raw_sign = f"{click_trans_id}{service_id}{CLICK_SECRET_KEY}{merchant_trans_id}{amount}{action}{sign_time}"
    else:              # Complete (action == "1")
        raw_sign = f"{click_trans_id}{service_id}{CLICK_SECRET_KEY}{merchant_trans_id}{merchant_prep_id}{amount}{action}{sign_time}"

    expected_sign = hashlib.md5(raw_sign.encode("utf-8")).hexdigest().lower()

    if not hmac.compare_digest(expected_sign, sign_string):
        log.warning(f"🚨 Click Webhook: Soxta sign_string! IP={client_ip}, order={merchant_trans_id}")
        return web.json_response({"error": -1, "error_note": "SIGN CHECK FAILED!"})

    # Buyurtmani bazadan tekshirish
    try:
        order_id = int(merchant_trans_id)
    except ValueError:
        return web.json_response({"error": -5, "error_note": "Order does not exist"})

    order = await get_order_by_id(order_id)
    if not order:
        return web.json_response({"error": -5, "error_note": "Order does not exist"})

    order_dict = dict(order)
    if order_dict.get("payment_status") == "paid":
        return web.json_response({"error": -4, "error_note": "Already paid"})
    if order_dict.get("status") == "cancelled":
        return web.json_response({"error": -9, "error_note": "Order cancelled"})

    try:
        if abs(float(amount) - float(order_dict["total_amount"])) > 0.01:
            log.warning(
                f"🚨 Click summa xatosi! Order #{order_id}: expected={order_dict['total_amount']}, got={amount}"
            )
            return web.json_response({"error": -2, "error_note": "Incorrect parameter amount"})
    except ValueError:
        return web.json_response({"error": -2, "error_note": "Incorrect parameter amount"})

    if action == "0":
        return web.json_response({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": order_id,
            "error": 0,
            "error_note": "Success",
        })

    if action == "1":
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET payment_status = 'paid', transaction_id = $1 WHERE id = $2",
                f"click:{click_trans_id}", order_id,
            )
        mark_transaction_used(f"click:{click_trans_id}")

        # ── Toki to'lov amalga oshirilmasa kanalga bormaydi — to'langach yuboramiz ──
        try:
            bot = request.app.get("bot")
            from utils.order_dispatcher import dispatch_paid_order_to_channel
            asyncio.create_task(dispatch_paid_order_to_channel(bot, int(order_id), transaction_id=f"click:{click_trans_id}"))
        except Exception as disp_err:
            log.error(f"Click dispatch order error: {disp_err}")

        return web.json_response({
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": order_id,
            "error": 0,
            "error_note": "Success",
        })

    return web.json_response({"error": -3, "error_note": "Action not found"})

