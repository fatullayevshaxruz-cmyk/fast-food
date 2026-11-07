"""
security/__init__.py
====================
Darxan Burger Bot & Mini App Kiberxavfsizlik Paketi.
"""

from .webapp_auth import (
    verify_telegram_init_data,
    verify_request_user,
    is_verified_admin,
)
from .rate_limiter import (
    rate_limiter,
    security_and_rate_limit_middleware,
    BotAntiFloodMiddleware,
    check_and_record_order_idempotency,
)
from .payment_guard import (
    sign_invoice_payload,
    verify_and_strip_invoice_payload,
    is_transaction_already_used,
    mark_transaction_used,
    verify_cart_payment_amount,
    payme_webhook_handler,
    click_webhook_handler,
)
from .sanitization import (
    sanitize_text,
    sanitize_phone,
    clamp_quantity,
    validate_coordinates,
    otp_store,
    MAX_CART_DISTINCT_ITEMS,
)

