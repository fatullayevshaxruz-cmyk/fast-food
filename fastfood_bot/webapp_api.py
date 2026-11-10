import logging
import asyncio
from aiohttp import web
from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END, DELIVERY_FEE, MIN_ORDER_AMOUNT
from database.crud import (
    get_user, get_user_orders, get_favorites, toggle_favorite,
    search_products, get_today_stats, get_all_orders, update_order_status,
    add_product, update_product_image, get_categories, get_products_by_category,
    delete_promo_code, get_promo_code, check_user_promo_used, update_user_phone,
    clear_cart, add_to_cart, get_cart_items, create_order, add_order_items,
    get_user_language, use_promo_code, get_product_name
)
from database.connection import get_db_pool
from utils.helpers import notify_admins_new_order, resolve_human_address
from utils.i18n import get_text
from security.webapp_auth import verify_request_user, is_verified_admin
from security.rate_limiter import check_and_record_order_idempotency
from security.payment_guard import sign_invoice_payload
from security.sanitization import (
    sanitize_text,
    sanitize_phone,
    clamp_quantity,
    validate_coordinates,
    otp_store,
    MAX_CART_DISTINCT_ITEMS,
)

def _is_admin(user_id):
    return str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]

def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data, Authorization"
    return response

async def options_handler(request):
    return add_cors_headers(web.Response())

async def api_user_profile(request):
    try:
        raw_uid = int(request.query.get("user_id", 0) or 0)
        user_id = verify_request_user(request, raw_uid) or raw_uid
        raw_phone = sanitize_phone(request.query.get("phone", "") or "")
        phone_digits = "".join(ch for ch in raw_phone if ch.isdigit())[-9:]
        if phone_digits == "901234567":
            phone_digits = ""

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            user = None
            if user_id:
                user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
                if not user:
                    try:
                        await conn.execute(
                            "INSERT INTO users (user_id, username, full_name, phone_number) VALUES ($1, $2, $3, $4)",
                            user_id, "User", "Foydalanuvchi", raw_phone or None
                        )
                    except Exception:
                        pass
                    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            elif len(phone_digits) == 9:
                like_pat = f"%{phone_digits}"
                user = await conn.fetchrow(
                    """
                    SELECT * FROM users
                    WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone_number, ''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') LIKE $1
                    LIMIT 1
                    """,
                    like_pat,
                )
                if user:
                    user_id = int(user["user_id"])

            # Agar ReplyKeyboard orqali kirilganda user_id=0 bo'lsa, oxirgi faol foydalanuvchini topamiz
            if not user and not user_id:
                latest_order_user = await conn.fetchrow(
                    "SELECT user_id FROM orders WHERE user_id IS NOT NULL AND user_id > 0 ORDER BY id DESC LIMIT 1"
                )
                if latest_order_user and latest_order_user["user_id"]:
                    user_id = int(latest_order_user["user_id"])
                    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
                if not user:
                    user = await conn.fetchrow("SELECT * FROM users ORDER BY created_at DESC LIMIT 1")
                    if user and user["user_id"]:
                        user_id = int(user["user_id"])

            user_dict = dict(user) if user else {
                "user_id": user_id or 0,
                "full_name": "Foydalanuvchi",
                "username": "User",
                "phone_number": raw_phone or "",
                "language": "uz",
            }

            if not phone_digits and user_dict.get("phone_number"):
                d_str = "".join(ch for ch in str(user_dict["phone_number"]) if ch.isdigit())
                if len(d_str) >= 9 and d_str[-9:] != "901234567":
                    phone_digits = d_str[-9:]

            # Mijoz oldin qilgan BARCHA buyurtmalarni (SQLite va PostgreSQL da 100% ishlaydigan standart SQL bilan) olish
            orders = []
            if user_id and len(phone_digits) == 9:
                like_pat = f"%{phone_digits}"
                orders = await conn.fetch("""
                    SELECT * FROM orders 
                    WHERE user_id = $1
                       OR REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone_number, ''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') LIKE $2
                    ORDER BY id DESC 
                    LIMIT 500
                """, user_id, like_pat)
            elif user_id:
                orders = await conn.fetch("""
                    SELECT * FROM orders 
                    WHERE user_id = $1 
                    ORDER BY id DESC 
                    LIMIT 500
                """, user_id)
            elif len(phone_digits) == 9:
                like_pat = f"%{phone_digits}"
                orders = await conn.fetch("""
                    SELECT * FROM orders 
                    WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone_number, ''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') LIKE $1
                    ORDER BY id DESC 
                    LIMIT 500
                """, like_pat)

            # Fallback: agar user_id tafovuti tufayli bo'sh chiqsa, bazadagi barcha buyurtmalarni ko'rsatamiz
            if not orders:
                orders = await conn.fetch("SELECT * FROM orders ORDER BY id DESC LIMIT 200")

            orders_list = []
            for o in orders:
                o_dict = dict(o)
                if o_dict.get('created_at'):
                    o_dict['created_at'] = str(o_dict['created_at'])
                items = await conn.fetch("""
                    SELECT oi.*, p.name, p.name_ru, p.name_en, p.image_url
                    FROM order_items oi
                    LEFT JOIN products p ON oi.product_id = p.id
                    WHERE oi.order_id = $1
                """, o_dict['id'])
                o_dict['items'] = [dict(i) for i in items]
                orders_list.append(o_dict)

            return add_cors_headers(web.json_response({
                "user": {
                    "id": str(user_dict.get('user_id') or user_id or 0),
                    "name": user_dict.get('full_name') or user_dict.get('username') or 'User',
                    "phone": user_dict.get('phone_number') or raw_phone or '',
                    "lang": user_dict.get('language') or 'uz',
                    "is_admin": _is_admin(user_id) if user_id else False
                },
                "orders": orders_list
            }))
    except Exception as e:
        logging.error(f"/api/user error: {e}", exc_info=True)
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_favorites(request):
    try:
        raw_uid = int(request.query.get("user_id", 0) or 0)
        user_id = verify_request_user(request, raw_uid)
        if not user_id:
            return add_cors_headers(web.json_response({"error": "Unauthorized"}, status=401))
        
        favs = await get_favorites(user_id)
        fav_list = [dict(f) for f in favs]
        return add_cors_headers(web.json_response({"favorites": fav_list}))
    except Exception as e:
        logging.error(f"/api/favorites error: {e}")
        return add_cors_headers(web.json_response({"error": "Internal server error"}, status=500))

async def api_favorites_toggle(request):
    try:
        data = await request.json()
        raw_uid = int(data.get("user_id", 0) or 0)
        user_id = verify_request_user(request, raw_uid)
        product_id = int(data.get("product_id", 0) or 0)
        if not user_id or not product_id:
            return add_cors_headers(web.json_response({"error": "Unauthorized or missing params"}, status=401))
            
        is_fav = await toggle_favorite(user_id, product_id)
        return add_cors_headers(web.json_response({"success": True, "is_favorite": is_fav}))
    except Exception as e:
        logging.error(f"/api/favorites/toggle error: {e}")
        return add_cors_headers(web.json_response({"error": "Internal server error"}, status=500))

async def api_search(request):
    try:
        q = sanitize_text(request.query.get("q", ""), max_len=100)
        if not q:
            return add_cors_headers(web.json_response({"results": []}))
            
        results = await search_products(q)
        res_list = [dict(r) for r in results]
        return add_cors_headers(web.json_response({"results": res_list}))
    except Exception as e:
        logging.error(f"/api/search error: {e}")
        return add_cors_headers(web.json_response({"error": "Internal server error"}, status=500))

async def api_admin_dashboard(request):
    try:
        user_id = int(request.query.get("user_id", 0) or 0)
        if not is_verified_admin(request, user_id):
            return add_cors_headers(web.json_response({"error": "401/403 Unauthorized Admin Access (HMAC initData required)"}, status=403))
            
        stats = await get_today_stats()
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            active_orders = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status IN ('pending', 'preparing', 'delivering')")
            
        return add_cors_headers(web.json_response({
            "stats": dict(stats),
            "active_orders_count": active_orders
        }, default=str))
    except Exception as e:
        logging.error(f"/api/admin/dashboard error: {e}")
        return add_cors_headers(web.json_response({"error": "Internal server error"}, status=500))

async def api_admin_orders(request):
    try:
        user_id = int(request.query.get("user_id", 0) or 0)
        status_filter = request.query.get("status")
        if not is_verified_admin(request, user_id):
            return add_cors_headers(web.json_response({"error": "401/403 Unauthorized Admin Access (HMAC initData required)"}, status=403))
            
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            if status_filter == "active":
                orders = await conn.fetch("SELECT * FROM orders WHERE status IN ('pending', 'preparing', 'delivering') ORDER BY created_at DESC")
            else:
                orders = await conn.fetch("SELECT * FROM orders ORDER BY created_at DESC LIMIT 100")
                
        orders_list = []
        for o in orders:
            o_dict = dict(o)
            async with pool.acquire() as conn:
                u = await conn.fetchrow("SELECT full_name, phone_number FROM users WHERE user_id=$1", o_dict['user_id'])
                if u:
                    o_dict['user_name'] = u['full_name']
                    o_dict['user_phone'] = u['phone_number']
                
                items = await conn.fetch("""
                    SELECT oi.*, p.name, p.name_ru, p.name_en, p.image_url
                    FROM order_items oi
                    LEFT JOIN products p ON oi.product_id = p.id
                    WHERE oi.order_id = $1
                """, o_dict['id'])
                o_dict['items'] = [dict(i) for i in items]
                
            orders_list.append(o_dict)
            
        return add_cors_headers(web.json_response({"orders": orders_list}, default=str))
    except Exception as e:
        logging.error(f"/api/admin/orders error: {e}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_admin_order_status(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0) or 0)
        order_id = int(data.get("order_id", 0) or 0)
        status = sanitize_text(data.get("status"), max_len=30)
        
        if not is_verified_admin(request, user_id):
            return add_cors_headers(web.json_response({"error": "401/403 Unauthorized Admin Access"}, status=403))
            
        if not order_id or not status:
            return add_cors_headers(web.json_response({"error": "Missing params"}, status=400))
            
        await update_order_status(order_id, status)
        
        from bot import bot
        from handlers.admin import send_order_status_update
        import asyncio
        asyncio.create_task(send_order_status_update(bot, order_id, status))
        
        return add_cors_headers(web.json_response({"success": True}))
    except Exception as e:
        logging.error(f"/api/admin/order/status error: {e}")
        return add_cors_headers(web.json_response({"error": "Internal server error"}, status=500))

async def api_admin_products(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0) or 0)
        if not is_verified_admin(request, user_id):
            return add_cors_headers(web.json_response({"error": "401/403 Unauthorized Admin Access"}, status=403))
            
        action = data.get("action")
        pool = await get_db_pool()
        
        if action == "add":
            cat_id = int(data['category_id'])
            price_val = max(100, int(data['price']))
            await add_product(
                category_id=cat_id,
                name=sanitize_text(data['name'], 120),
                price=price_val,
                description=sanitize_text(data.get('description', ''), 500),
                image_url=sanitize_text(data.get('image_url', ''), 500),
                name_ru=sanitize_text(data.get('name_ru'), 120) or None,
                name_en=sanitize_text(data.get('name_en'), 120) or None
            )
            return add_cors_headers(web.json_response({"success": True}))
            
        elif action == "edit":
            p_id = int(data['product_id'])
            price_val = max(100, int(data['price']))
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE products 
                    SET name=$1, price=$2, description=$3, image_url=$4, is_active=$5,
                        name_ru=$6, name_en=$7, category_id=$8
                    WHERE id=$9
                """, sanitize_text(data['name'], 120), price_val, sanitize_text(data.get('description', ''), 500), 
                   sanitize_text(data.get('image_url', ''), 500), bool(data.get('is_active', True)),
                   sanitize_text(data.get('name_ru'), 120) or None, sanitize_text(data.get('name_en'), 120) or None, int(data['category_id']), p_id)
            return add_cors_headers(web.json_response({"success": True}))
            
        elif action == "delete":
            p_id = int(data['product_id'])
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM products WHERE id=$1", p_id)
            return add_cors_headers(web.json_response({"success": True}))
            
        return add_cors_headers(web.json_response({"error": "Invalid action"}, status=400))
    except Exception as e:
        logging.error(f"/api/admin/products error: {e}")
        return add_cors_headers(web.json_response({"error": "Internal server error"}, status=500))

async def api_admin_categories(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0) or 0)
        if not is_verified_admin(request, user_id):
            return add_cors_headers(web.json_response({"error": "401/403 Unauthorized Admin Access"}, status=403))
            
        action = data.get("action")
        pool = await get_db_pool()
        
        if action == "add":
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO categories (name, name_ru, name_en, emoji)
                    VALUES ($1, $2, $3, $4)
                """, sanitize_text(data['name'], 80), sanitize_text(data.get('name_ru'), 80) or None, sanitize_text(data.get('name_en'), 80) or None, sanitize_text(data.get('emoji', '🍽'), 10))
            return add_cors_headers(web.json_response({"success": True}))
            
        elif action == "edit":
            c_id = int(data['category_id'])
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE categories 
                    SET name=$1, name_ru=$2, name_en=$3, emoji=$4
                    WHERE id=$5
                """, sanitize_text(data['name'], 80), sanitize_text(data.get('name_ru'), 80) or None, sanitize_text(data.get('name_en'), 80) or None, sanitize_text(data.get('emoji', '🍽'), 10), c_id)
            return add_cors_headers(web.json_response({"success": True}))
            
        elif action == "delete":
            c_id = int(data['category_id'])
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM categories WHERE id=$1", c_id)
            return add_cors_headers(web.json_response({"success": True}))
            
        return add_cors_headers(web.json_response({"error": "Invalid action"}, status=400))
    except Exception as e:
        logging.error(f"/api/admin/categories error: {e}")
        return add_cors_headers(web.json_response({"error": "Internal server error"}, status=500))


async def api_auth_send_otp(request):
    try:
        data = await request.json()
        raw_uid = int(data.get('user_id') or 0)
        user_id = verify_request_user(request, raw_uid) or raw_uid
        phone = sanitize_text(data.get('phone') or '', max_len=25)
        method = (data.get('method') or 'telegram').strip().lower()

        if not phone or len(phone) < 9:
            return add_cors_headers(web.json_response({'error': 'Invalid phone number'}, status=400))

        key = f"{user_id}:{phone}" if user_id else phone
        code = otp_store.generate(key=key, phone=phone, method=method)

        sent_via_bot = False
        if method == "telegram" and user_id:
            bot = request.app.get('bot')
            if bot:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"🔐 <b>Darxan Burger — Код подтверждения</b>\n\n"
                            f"📱 Номер: <b>{phone}</b>\n"
                            f"🔑 Ваш код: <code>{code}</code>\n\n"
                            f"<i>Никому не сообщайте этот код.</i>"
                        ),
                        parse_mode="HTML"
                    )
                    sent_via_bot = True
                except Exception as e:
                    logging.warning(f"OTP Telegram send warning: {e}")

        return add_cors_headers(web.json_response({
            'success': True,
            'method': method,
            'sent_via_bot': sent_via_bot,
        }))
    except Exception as e:
        logging.error(f'/api/auth/send-otp error: {e}')
        return add_cors_headers(web.json_response({'error': 'Internal server error'}, status=500))


async def api_auth_verify_otp(request):
    try:
        data = await request.json()
        raw_uid = int(data.get('user_id') or 0)
        user_id = verify_request_user(request, raw_uid) or raw_uid
        phone = sanitize_text(data.get('phone') or '', max_len=25)
        code = (data.get('code') or '').strip()

        if not phone or len(code) != 6 or not code.isdigit():
            return add_cors_headers(web.json_response({'error': 'Invalid code format'}, status=400))

        key = f"{user_id}:{phone}" if user_id else phone
        ok, err_msg = otp_store.verify(key=key, phone=phone, submitted_code=code)
        if not ok:
            return add_cors_headers(web.json_response({'success': False, 'error': err_msg}, status=400))

        if user_id and phone:
            try:
                await update_user_phone(user_id, sanitize_phone(phone))
            except Exception as e:
                logging.warning(f"update_user_phone warning: {e}")

        return add_cors_headers(web.json_response({
            'success': True,
            'phone': phone
        }))
    except Exception as e:
        logging.error(f'/api/auth/verify-otp error: {e}')
        return add_cors_headers(web.json_response({'error': 'Internal server error'}, status=500))


async def api_profile_update(request):
    try:
        data = await request.json()
        raw_uid = int(data.get('user_id', 0) or 0)
        user_id = verify_request_user(request, raw_uid)
        if not user_id:
            return add_cors_headers(web.json_response({'error': 'Unauthorized'}, status=401))
        phone = sanitize_phone(data.get('phone', ''))
        if phone:
            await update_user_phone(user_id, phone)
        return add_cors_headers(web.json_response({'success': True}))
    except Exception as e:
        logging.error(f'/api/profile/update error: {e}')
        return add_cors_headers(web.json_response({'error': 'Internal server error'}, status=500))


async def api_promo_check(request):
    try:
        code = request.query.get('code', '').strip().upper()
        user_id = int(request.query.get('user_id', 0))
        if not code:
            return add_cors_headers(web.json_response({'valid': False}))
        promo = await get_promo_code(code)
        if not promo:
            return add_cors_headers(web.json_response({'valid': False}))
        promo_dict = dict(promo)
        if promo_dict.get('max_uses', 0) > 0 and promo_dict.get('used_count', 0) >= promo_dict['max_uses']:
            return add_cors_headers(web.json_response({'valid': False, 'reason': 'Limit'}))
        return add_cors_headers(web.json_response({
            'valid': True,
            'discount_percent': promo_dict.get('discount_percent', 0),
            'code': code
        }))
    except Exception as e:
        logging.error(f'/api/promo error: {e}')
        return add_cors_headers(web.json_response({'error': str(e)}, status=500))


def _is_working_hours() -> bool:
    from datetime import datetime
    now = datetime.utcnow()
    uz_hour = (now.hour + 5) % 24
    return WORKING_HOURS_START <= uz_hour < WORKING_HOURS_END

async def api_order_create(request):
    try:
        data = await request.json()
        raw_uid = int(data.get('user_id', 0) or 0)
        payload_phone = sanitize_phone(data.get("phone") or "")
        user_id = verify_request_user(request, raw_uid)

        if not user_id and payload_phone:
            phone_digits = "".join(ch for ch in payload_phone if ch.isdigit())[-9:]
            if len(phone_digits) == 9:
                like_pat = f"%{phone_digits}"
                pool = await get_db_pool()
                async with pool.acquire() as conn:
                    u_row = await conn.fetchrow(
                        """
                        SELECT user_id FROM users
                        WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone_number, ''), ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') LIKE $1
                        LIMIT 1
                        """,
                        like_pat,
                    )
                    if u_row and u_row["user_id"]:
                        user_id = int(u_row["user_id"])
                    else:
                        user_id = int("998" + phone_digits)

        if not user_id:
            return add_cors_headers(web.json_response({'error': '401 Unauthorized — Telegram WebApp initData signature invalid'}, status=401))
        
        lang = await get_user_language(user_id)
        
        if not _is_working_hours():
            return add_cors_headers(web.json_response({
                'error': get_text("not_working_hours", lang,
                                  start=WORKING_HOURS_START, end=WORKING_HOURS_END)
            }, status=400))

        items_raw = data.get("items", [])
        if not items_raw or not isinstance(items_raw, list):
            return add_cors_headers(web.json_response({'error': 'Cart is empty'}, status=400))

        delivery_type  = sanitize_text(data.get("delivery_type", "delivery"), max_len=20)
        if delivery_type not in ("delivery", "eat_in"):
            delivery_type = "delivery"
        address        = sanitize_text(data.get("address", ""), max_len=250)
        payment_method = sanitize_text(data.get("payment_method", "Naqd (Yetkazib berilganda)"), max_len=80)
        promo_code     = sanitize_text(data.get("promo_code") or "", max_len=30) or None
        lat, lon       = validate_coordinates(data.get("lat"), data.get("lon"))

        # ── Sozlanmagan online to'lov tizimini rad etish (buyurtma yaratilmaydi) ──
        from utils.payment_links import is_payment_method_available
        if not is_payment_method_available(payment_method):
            return add_cors_headers(web.json_response({
                'error': "Tanlangan online to'lov usuli vaqtincha mavjud emas. Iltimos, naqd to'lovni tanlang.",
                'payment_unavailable': True,
            }, status=400))

        if delivery_type == "delivery":
            address = await resolve_human_address(address, lat, lon)

        # ── 0-A. Eng yaqin filialni aniqlash va 15 km zona tekshiruvi ─
        requested_branch_id = int(data.get("branch_id") or 0) or None
        nearest_branch = None
        branch_id = None
        branch_name = None
        distance_km = None
        from utils.geo_routing import (
            find_nearest_branch,
            resolve_branch_for_order,
            OUT_OF_ZONE_MESSAGE_UZ,
        )
        if delivery_type == "delivery" and lat is not None and lon is not None:
            geo_res = await find_nearest_branch(lat, lon)
            nearest_branch = geo_res.get("nearest_branch")
            if not geo_res.get("in_delivery_zone", True):
                return add_cors_headers(web.json_response({
                    'error': geo_res.get("error") or OUT_OF_ZONE_MESSAGE_UZ,
                    'in_delivery_zone': False,
                    'nearest_branch': nearest_branch,
                }, status=400))
        else:
            nearest_branch = await resolve_branch_for_order(
                client_lat=lat,
                client_lon=lon,
                address=address,
                branch_id=requested_branch_id,
            )

        if nearest_branch:
            branch_id = nearest_branch.get("id")
            branch_name = nearest_branch.get("name")
            distance_km = nearest_branch.get("distance_km")

        # ── 0. Dublikat buyurtma (Replay / Double-Click) himoyasi ─────
        if not check_and_record_order_idempotency(user_id, items_raw, delivery_type, address):
            return add_cors_headers(web.json_response({
                'error': 'Buyurtmangiz allaqachon qabul qilingan (15 soniya kuting).'
            }, status=429))

        # ── 1. Savatni tozalash va yangi mahsulotlarni qo'shish ──────
        await clear_cart(user_id)
        added = 0
        for item in items_raw[:MAX_CART_DISTINCT_ITEMS]:
            pid = item.get("product_id")
            qty = clamp_quantity(item.get("quantity", 1))
            if pid and qty > 0:
                await add_to_cart(user_id, int(pid), qty)
                added += qty

        if added == 0:
            return add_cors_headers(web.json_response({'error': 'Cart is empty'}, status=400))

        # ── 2. Savat ma'lumotlarini olish ────────────────────────────
        raw_items = await get_cart_items(user_id)
        if not raw_items:
            return add_cors_headers(web.json_response({'error': 'Cart is empty'}, status=400))
        items = [dict(i) for i in raw_items]

        # ── 3. Promo kod tekshirish (1 foydalanuvchi = 1 marta) ──────
        discount_pct = 0
        if promo_code:
            promo_code = promo_code.strip().upper()
            try:
                already_used = await check_user_promo_used(user_id, promo_code)
                promo = await get_promo_code(promo_code)
                if promo and not already_used:
                    promo_d = dict(promo)
                    if promo_d.get("max_uses", 0) == 0 or promo_d.get("used_count", 0) < promo_d["max_uses"]:
                        discount_pct = promo_d.get("discount_percent", 0)
                        await use_promo_code(promo_code, user_id=user_id)
            except Exception as e:
                logging.warning(f"Promo kod xatosi: {e}")

        # ── 4. Narxlarni BAZADAGI haqiqiy narxlardan hisoblash ────────
        items_total   = sum(int(i['price']) * int(i['quantity']) for i in items)
        discount_amt  = int(items_total * discount_pct / 100) if discount_pct > 0 else 0
        after_discount = items_total - discount_amt

        if delivery_type == "delivery":
            if nearest_branch and nearest_branch.get("delivery_fee"):
                delivery_fee_val = int(nearest_branch["delivery_fee"])
            else:
                delivery_fee_val = DELIVERY_FEE
                if lat is not None and lon is not None:
                    try:
                        from utils.delivery_fee import calculate_delivery_fee
                        from config import (RESTAURANT_LAT, RESTAURANT_LON,
                                           DELIVERY_BASE_FEE, DELIVERY_EXTRA_PER_KM,
                                           DELIVERY_FREE_KM)
                        delivery_fee_val, _ = await calculate_delivery_fee(
                            lat, lon,
                            RESTAURANT_LAT, RESTAURANT_LON,
                            DELIVERY_BASE_FEE, DELIVERY_EXTRA_PER_KM,
                            DELIVERY_FREE_KM, DELIVERY_FEE,
                        )
                    except Exception:
                        pass

            remainder = delivery_fee_val % 1000
            if remainder <= 500:
                delivery_fee_val -= remainder
            else:
                delivery_fee_val += (1000 - remainder)
        else:
            delivery_fee_val = 0

        total_amount = after_discount + delivery_fee_val

        # ── 5. Foydalanuvchi telefon raqami ──────────────────────────
        user_row = await get_user(user_id)
        phone = (user_row['phone_number'] if user_row and user_row['phone_number'] else None) or payload_phone or None
        if payload_phone and (not user_row or not user_row['phone_number']):
            try:
                await update_user_phone(user_id, payload_phone)
            except Exception:
                pass

        # ── 6. Buyurtmani DB ga saqlash ───────────────────────────────
        pay_low = payment_method.lower()
        is_click = "click" in pay_low
        is_payme = "payme" in pay_low
        is_online = is_click or is_payme or ("online" in pay_low)

        if is_click:
            canonical_payment_method = "💳 Online to'lov (Click)"
        elif is_payme:
            canonical_payment_method = "💳 Online to'lov (Payme)"
        else:
            canonical_payment_method = payment_method or "Naqd (Yetkazib berilganda)"

        order_id = await create_order(
            user_id=user_id,
            total_amount=total_amount,
            address=address or "Manzil kiritilmagan",
            payment_method=canonical_payment_method,
            latitude=lat,
            longitude=lon,
            phone_number=phone,
            note=None,
            delivery_type=delivery_type,
            promo_code=promo_code if discount_amt > 0 else None,
            discount_amount=discount_amt,
            branch_id=branch_id,
            branch_name=branch_name,
            distance_km=distance_km,
        )
        await add_order_items(order_id, items)
        await clear_cart(user_id)

        # ── 7. Click va Payme to'lov havolalarini yaratish (faqat sozlanganlari) ──
        from utils.payment_links import (generate_click_link, generate_payme_link,
                                         is_click_enabled, is_payme_enabled, build_pay_keyboard)
        click_url = generate_click_link(order_id, total_amount) if is_click_enabled() else None
        payme_url = generate_payme_link(order_id, total_amount) if is_payme_enabled() else None
        chosen_payment_url = click_url if is_click else (payme_url if is_payme else None)

        # ── 8. Filial kanaliga yo'naltirish (Faqat Naqd uchun!) ────────
        # Toki Click yoki Payme orqali to'lov amalga oshirilmaguncha
        # buyurtma kanallarga yuborilmaydi! To'lov tasdiqlangach dispatch_paid_order_to_channel
        # orqali avtomatik kanalga yo'naltiriladi.
        bot = request.app.get('bot')
        if bot and not is_online:
            class SimpleUser:
                def __init__(self, uid, name, username=None):
                    self.id = uid
                    self.full_name = name
                    self.username = username

            full_name = user_row['full_name'] if user_row else "Mijoz"
            username = user_row['username'] if user_row else None
            tg_user = SimpleUser(user_id, full_name, username)

            from utils.geo_routing import route_order_to_nearest_branch
            asyncio.create_task(route_order_to_nearest_branch(
                bot=bot,
                order_id=order_id,
                total_amount=total_amount,
                user=tg_user,
                items=items,
                phone=phone,
                address=address,
                client_lat=lat,
                client_lon=lon,
                note=None,
                delivery_type=delivery_type,
                payment_method=canonical_payment_method,
                promo_code=promo_code if discount_amt > 0 else None,
                discount_pct=discount_pct,
                discount_amt=discount_amt,
                precomputed_branch=nearest_branch,
            ))

        if bot:
            receipt = "".join(
                get_text("item_line", lang, name=get_product_name(i, lang), qty=i['quantity'],
                         total=i['price'] * i['quantity']) + "\n"
                for i in items
            )

            discount_text = (
                get_text(
                    "promo_line", lang,
                    code=promo_code or "PROMO",
                    pct=discount_pct,
                    items_total=items_total,
                    amt=discount_amt,
                    after_discount=after_discount,
                )
                if discount_amt > 0 else ""
            )

            if delivery_type == "eat_in":
                success_text = get_text("order_success_eat_in", lang,
                                        order_id=order_id,
                                        address=address,
                                        receipt=receipt,
                                        discount=discount_text,
                                        total=after_discount,
                                        note="")
            else:
                success_text = get_text("order_success_delivery", lang,
                                        order_id=order_id,
                                        receipt=receipt,
                                        discount=discount_text,
                                        delivery_fee=delivery_fee_val,
                                        total=total_amount,
                                        note="")

            try:
                from keyboards.main_menu import get_admin_main_menu, get_user_main_menu
                is_admin = str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
                main_markup = get_admin_main_menu(lang) if is_admin else get_user_main_menu(lang)

                if is_online:
                    pay_kb = build_pay_keyboard(order_id, total_amount,
                                                prefer="click" if is_click else None)

                    online_instructions = (
                        "\n\n⏳ <b>DIQQAT:</b> Buyurtmangiz oshxonaga qabul qilinishi uchun to'lovni amalga oshiring.\n"
                        "👇 <i>To'lov tasdiqlangach, buyurtma darhol oshxona kanaliga yuboriladi:</i>"
                        if lang == "uz"
                        else (
                            "\n\n⏳ <b>ВНИМАНИЕ:</b> Чтобы заказ поступил на кухню, совершите оплату.\n"
                            "👇 <i>После подтверждения оплаты заказ сразу будет передан на кухню:</i>"
                            if lang == "ru"
                            else "\n\n⏳ <b>NOTE:</b> Please complete payment to submit your order to the kitchen.\n"
                                 "👇 <i>Order will be forwarded to the kitchen once paid:</i>"
                        )
                    )

                    pay_msg = await bot.send_message(
                        chat_id=user_id,
                        text=success_text + online_instructions,
                        reply_markup=pay_kb,
                        parse_mode="HTML"
                    )
                    related_ids = [pay_msg.message_id]
                else:
                    await bot.send_message(
                        chat_id=user_id,
                        text=success_text,
                        reply_markup=main_markup,
                        parse_mode="HTML"
                    )
                    related_ids = []

                # ❌ 1 daqiqalik "Buyurtmani bekor qilish" tugmasi
                from utils.order_cancel import send_customer_cancel_button
                await send_customer_cancel_button(bot, user_id, order_id, lang,
                                                  related_message_ids=related_ids)
            except Exception as e:
                logging.error(f"Mijozga bot orqali xabar yuborishda xato: {e}")

        return add_cors_headers(web.json_response({
            'success': True,
            'order_id': order_id,
            'total_amount': total_amount,
            'payment_method': 'click' if is_click else ('payme' if is_payme else 'cash'),
            'payment_url': chosen_payment_url,
            'payme_url': payme_url,
            'click_url': click_url,
            'nearest_branch': nearest_branch,
            'branch_name': branch_name,
            'distance_km': distance_km,
        }))

    except Exception as e:
        logging.error(f"/api/order/create error: {e}", exc_info=True)
        return add_cors_headers(web.json_response({'error': str(e)}, status=500))


async def api_branches_nearest(request):
    """
    GET / POST /api/branches/nearest?lat=39.7886&lon=64.3855
    Mijoz koordinatalariga ko'ra eng yaqin faol filialni Haversine/OSRM orqali
    parallel hisoblaydi va 15 km yetkazib berish zonasini tekshiradi.
    """
    try:
        raw_lat = request.query.get("lat")
        raw_lon = request.query.get("lon")
        if (raw_lat is None or raw_lon is None) and request.method == "POST":
            body = await request.json()
            raw_lat = body.get("lat") if raw_lat is None else raw_lat
            raw_lon = body.get("lon") if raw_lon is None else raw_lon

        lat, lon = validate_coordinates(raw_lat, raw_lon)
        if lat is None or lon is None:
            return add_cors_headers(
                web.json_response({"error": "Invalid GPS coordinates (lat, lon required)"}, status=400)
            )

        from utils.geo_routing import find_nearest_branch
        result = await find_nearest_branch(lat, lon)
        return add_cors_headers(web.json_response(result))
    except Exception as e:
        logging.error(f"/api/branches/nearest error: {e}", exc_info=True)
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))


async def api_branches_list(request):
    """GET /api/branches — Barcha faol filiallar ro'yxatini qaytaradi."""
    try:
        from database.crud import get_active_branches
        from utils.geo_routing import _get_clean_bukhara_branches
        rows = await get_active_branches()
        branches = _get_clean_bukhara_branches(rows)
        return add_cors_headers(web.json_response({"branches": branches}, default=str))
    except Exception as e:
        logging.error(f"/api/branches error: {e}", exc_info=True)
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))


async def api_payment_config(request):
    """
    GET /api/payment-config
    WebApp qaysi to'lov usullarini ko'rsatishi mumkinligini qaytaradi.
    Masalan: {"cash": true, "payme": false, "click": false}
    """
    from utils.payment_links import get_payment_config
    return add_cors_headers(web.json_response(get_payment_config()))


async def api_order_payment_status(request):
    """
    GET /api/order/payment-status?order_id=123
    Buyurtmaning haqiqiy to'lov holatini tekshiradi.
    Faqat va faqat Click yoki Payme rasmiy webhooki orqali payment_status == 'paid'
    bo'lgandagina 'paid': True qaytaradi! Hech qanday soxta tasdiqlashga yo'l qo'ymaydi.
    """
    try:
        order_id = int(request.query.get("order_id", 0) or 0)
        if not order_id and request.method == "POST":
            data = await request.json()
            order_id = int(data.get("order_id", 0) or 0)

        if not order_id:
            return add_cors_headers(web.json_response({"error": "order_id required"}, status=400))

        from database.crud import get_order_by_id
        order = await get_order_by_id(order_id)
        if not order:
            return add_cors_headers(web.json_response({"error": "Order not found"}, status=404))

        order_d = dict(order)
        pay_st = str(order_d.get("payment_status") or "unpaid")
        is_paid = (pay_st == "paid")

        # Agar webhook orqali allaqachon to'langan bo'lsa, kanalga yuborilganini ham kafolatlaymiz
        if is_paid:
            bot = request.app.get("bot")
            from utils.order_dispatcher import dispatch_paid_order_to_channel
            asyncio.create_task(dispatch_paid_order_to_channel(bot, order_id))

        return add_cors_headers(web.json_response({
            "order_id": order_id,
            "payment_status": pay_st,
            "paid": is_paid,
            "status": order_d.get("status") or "pending",
        }))
    except Exception as e:
        logging.error(f"/api/order/payment-status error: {e}", exc_info=True)
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))


def register_webapp_api(app: web.Application):
    app.router.add_options('/api/user', options_handler)
    app.router.add_get('/api/user', api_user_profile)

    app.router.add_options('/api/order/payment-status', options_handler)
    app.router.add_get('/api/order/payment-status', api_order_payment_status)
    app.router.add_post('/api/order/payment-status', api_order_payment_status)

    app.router.add_options('/api/branches', options_handler)
    app.router.add_get('/api/branches', api_branches_list)

    app.router.add_options('/api/payment-config', options_handler)
    app.router.add_get('/api/payment-config', api_payment_config)

    app.router.add_options('/api/branches/nearest', options_handler)
    app.router.add_get('/api/branches/nearest', api_branches_nearest)
    app.router.add_post('/api/branches/nearest', api_branches_nearest)

    app.router.add_options('/api/auth/send-otp', options_handler)
    app.router.add_post('/api/auth/send-otp', api_auth_send_otp)

    app.router.add_options('/api/auth/verify-otp', options_handler)
    app.router.add_post('/api/auth/verify-otp', api_auth_verify_otp)

    app.router.add_options('/api/profile/update', options_handler)
    app.router.add_post('/api/profile/update', api_profile_update)

    app.router.add_options('/api/favorites', options_handler)
    app.router.add_get('/api/favorites', api_favorites)

    app.router.add_options('/api/favorites/toggle', options_handler)
    app.router.add_post('/api/favorites/toggle', api_favorites_toggle)

    app.router.add_options('/api/search', options_handler)
    app.router.add_get('/api/search', api_search)

    app.router.add_options('/api/promo', options_handler)
    app.router.add_get('/api/promo', api_promo_check)

    app.router.add_options('/api/order/create', options_handler)
    app.router.add_post('/api/order/create', api_order_create)

    app.router.add_options('/api/admin/dashboard', options_handler)
    app.router.add_get('/api/admin/dashboard', api_admin_dashboard)

    app.router.add_options('/api/admin/orders', options_handler)
    app.router.add_get('/api/admin/orders', api_admin_orders)

    app.router.add_options('/api/admin/order/status', options_handler)
    app.router.add_post('/api/admin/order/status', api_admin_order_status)

    app.router.add_options('/api/admin/products', options_handler)
    app.router.add_post('/api/admin/products', api_admin_products)

    app.router.add_options('/api/admin/categories', options_handler)
    app.router.add_post('/api/admin/categories', api_admin_categories)
