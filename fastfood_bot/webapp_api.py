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
from utils.helpers import notify_admins_new_order
from utils.i18n import get_text

def _is_admin(user_id):
    return str(user_id) in [a.strip() for a in ADMIN_ID.split(",") if a.strip()]

def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

async def options_handler(request):
    return add_cors_headers(web.Response())

async def api_user_profile(request):
    try:
        user_id = int(request.query.get("user_id", 0))
        if not user_id:
            return add_cors_headers(web.json_response({"error": "Missing user_id"}, status=400))
        
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not user:
                try:
                    await conn.execute(
                        "INSERT INTO users (user_id, username, full_name) VALUES ($1, $2, $3)",
                        user_id, "User", "Foydalanuvchi"
                    )
                except Exception:
                    pass
                user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            
            orders = await conn.fetch("""
                SELECT * FROM orders 
                WHERE user_id = $1 
                ORDER BY created_at DESC 
                LIMIT 50
            """, user_id)
            
            user_dict = dict(user)
            orders_list = []
            for o in orders:
                o_dict = dict(o)
                items = await conn.fetch("SELECT * FROM order_items WHERE order_id = $1", o_dict['id'])
                o_dict['items'] = [dict(i) for i in items]
                orders_list.append(o_dict)
            
            return add_cors_headers(web.json_response({
                "user": {
                    "id": str(user_dict['user_id']),
                    "name": user_dict.get('full_name') or user_dict.get('username') or 'User',
                    "phone": user_dict.get('phone_number') or '',
                    "lang": user_dict.get('language') or 'uz',
                    "is_admin": _is_admin(user_id)
                },
                "orders": orders_list
            }, default=str))
    except Exception as e:
        logging.error(f"/api/user error: {e}", exc_info=True)
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_favorites(request):
    try:
        user_id = int(request.query.get("user_id", 0))
        if not user_id:
            return add_cors_headers(web.json_response({"error": "Missing user_id"}, status=400))
        
        favs = await get_favorites(user_id)
        fav_list = [dict(f) for f in favs]
        return add_cors_headers(web.json_response({"favorites": fav_list}))
    except Exception as e:
        logging.error(f"/api/favorites error: {e}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_favorites_toggle(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        product_id = int(data.get("product_id", 0))
        if not user_id or not product_id:
            return add_cors_headers(web.json_response({"error": "Missing params"}, status=400))
            
        is_fav = await toggle_favorite(user_id, product_id)
        return add_cors_headers(web.json_response({"success": True, "is_favorite": is_fav}))
    except Exception as e:
        logging.error(f"/api/favorites/toggle error: {e}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_search(request):
    try:
        q = request.query.get("q", "").strip()
        if not q:
            return add_cors_headers(web.json_response({"results": []}))
            
        results = await search_products(q)
        res_list = [dict(r) for r in results]
        return add_cors_headers(web.json_response({"results": res_list}))
    except Exception as e:
        logging.error(f"/api/search error: {e}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_admin_dashboard(request):
    try:
        user_id = int(request.query.get("user_id", 0))
        if not _is_admin(user_id):
            return add_cors_headers(web.json_response({"error": "Forbidden"}, status=403))
            
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
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_admin_orders(request):
    try:
        user_id = int(request.query.get("user_id", 0))
        status_filter = request.query.get("status")
        if not _is_admin(user_id):
            return add_cors_headers(web.json_response({"error": "Forbidden"}, status=403))
            
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
                
                items = await conn.fetch("SELECT * FROM order_items WHERE order_id = $1", o_dict['id'])
                o_dict['items'] = [dict(i) for i in items]
                
            orders_list.append(o_dict)
            
        return add_cors_headers(web.json_response({"orders": orders_list}, default=str))
    except Exception as e:
        logging.error(f"/api/admin/orders error: {e}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_admin_order_status(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        order_id = int(data.get("order_id", 0))
        status = data.get("status")
        
        if not _is_admin(user_id):
            return add_cors_headers(web.json_response({"error": "Forbidden"}, status=403))
            
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
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_admin_products(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        if not _is_admin(user_id):
            return add_cors_headers(web.json_response({"error": "Forbidden"}, status=403))
            
        action = data.get("action")
        pool = await get_db_pool()
        
        if action == "add":
            cat_id = int(data['category_id'])
            await add_product(
                category_id=cat_id,
                name=data['name'],
                price=int(data['price']),
                description=data.get('description', ''),
                image_url=data.get('image_url', ''),
                name_ru=data.get('name_ru'),
                name_en=data.get('name_en')
            )
            return add_cors_headers(web.json_response({"success": True}))
            
        elif action == "edit":
            p_id = int(data['product_id'])
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE products 
                    SET name=$1, price=$2, description=$3, image_url=$4, is_active=$5,
                        name_ru=$6, name_en=$7, category_id=$8
                    WHERE id=$9
                """, data['name'], int(data['price']), data.get('description', ''), 
                   data.get('image_url', ''), bool(data.get('is_active', True)),
                   data.get('name_ru'), data.get('name_en'), int(data['category_id']), p_id)
            return add_cors_headers(web.json_response({"success": True}))
            
        elif action == "delete":
            p_id = int(data['product_id'])
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM products WHERE id=$1", p_id)
            return add_cors_headers(web.json_response({"success": True}))
            
        return add_cors_headers(web.json_response({"error": "Invalid action"}, status=400))
    except Exception as e:
        logging.error(f"/api/admin/products error: {e}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_admin_categories(request):
    try:
        data = await request.json()
        user_id = int(data.get("user_id", 0))
        if not _is_admin(user_id):
            return add_cors_headers(web.json_response({"error": "Forbidden"}, status=403))
            
        action = data.get("action")
        pool = await get_db_pool()
        
        if action == "add":
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO categories (name, name_ru, name_en, emoji)
                    VALUES ($1, $2, $3, $4)
                """, data['name'], data.get('name_ru'), data.get('name_en'), data.get('emoji', '🍽'))
            return add_cors_headers(web.json_response({"success": True}))
            
        elif action == "edit":
            c_id = int(data['category_id'])
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE categories 
                    SET name=$1, name_ru=$2, name_en=$3, emoji=$4
                    WHERE id=$5
                """, data['name'], data.get('name_ru'), data.get('name_en'), data.get('emoji', '🍽'), c_id)
            return add_cors_headers(web.json_response({"success": True}))
            
        elif action == "delete":
            c_id = int(data['category_id'])
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM categories WHERE id=$1", c_id)
            return add_cors_headers(web.json_response({"success": True}))
            
        return add_cors_headers(web.json_response({"error": "Invalid action"}, status=400))
    except Exception as e:
        logging.error(f"/api/admin/categories error: {e}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500))

async def api_profile_update(request):
    try:
        data = await request.json()
        user_id = int(data.get('user_id', 0))
        if not user_id:
            return add_cors_headers(web.json_response({'error': 'Missing user_id'}, status=400))
        phone = data.get('phone', '').strip()
        if phone:
            await update_user_phone(user_id, phone)
        return add_cors_headers(web.json_response({'success': True}))
    except Exception as e:
        logging.error(f'/api/profile/update error: {e}')
        return add_cors_headers(web.json_response({'error': str(e)}, status=500))


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
        user_id = int(data.get('user_id', 0))
        if not user_id:
            return add_cors_headers(web.json_response({'error': 'Missing user_id'}, status=400))
        
        lang = await get_user_language(user_id)
        
        if not _is_working_hours():
            return add_cors_headers(web.json_response({
                'error': get_text("not_working_hours", lang,
                                  start=WORKING_HOURS_START, end=WORKING_HOURS_END)
            }, status=400))

        items_raw = data.get("items", [])
        if not items_raw:
            return add_cors_headers(web.json_response({'error': 'Cart is empty'}, status=400))

        # ── 1. Savatni tozalash va yangi mahsulotlarni qo'shish ──────
        await clear_cart(user_id)
        added = 0
        for item in items_raw:
            pid = item.get("product_id")
            qty = max(1, int(item.get("quantity", 1)))
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

        delivery_type  = data.get("delivery_type", "delivery")
        address        = data.get("address", "")
        payment_method = data.get("payment_method", "Naqd (Yetkazib berilganda)")
        promo_code     = data.get("promo_code") or None
        lat            = data.get("lat")
        lon            = data.get("lon")

        if lat is not None: lat = float(lat)
        if lon is not None: lon = float(lon)

        # ── 3. Promo kod tekshirish ───────────────────────────────────
        discount_pct = 0
        if promo_code:
            try:
                promo = await get_promo_code(promo_code.upper())
                if promo:
                    promo_d = dict(promo)
                    already_used = await check_user_promo_used(user_id, promo_code.upper())
                    if not already_used:
                        if promo_d.get("max_uses", 0) == 0 or promo_d.get("used_count", 0) < promo_d["max_uses"]:
                            discount_pct = promo_d.get("discount_percent", 0)
                            await use_promo_code(promo_code.upper(), user_id=user_id)
            except Exception as e:
                logging.warning(f"Promo kod xatosi: {e}")

        # ── 4. Narxlarni hisoblash ────────────────────────────────────
        items_total   = sum(i['price'] * i['quantity'] for i in items)
        discount_amt  = int(items_total * discount_pct / 100) if discount_pct > 0 else 0
        after_discount = items_total - discount_amt

        if delivery_type == "delivery":
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
        phone = user_row['phone_number'] if user_row else None

        # ── 6. Buyurtmani DB ga saqlash ───────────────────────────────
        order_id = await create_order(
            user_id=user_id,
            total_amount=total_amount,
            address=address or "Manzil kiritilmagan",
            payment_method=payment_method,
            latitude=lat,
            longitude=lon,
            phone_number=phone,
            note=None,
            delivery_type=delivery_type,
        )
        await add_order_items(order_id, items)
        await clear_cart(user_id)

        # ── 7. Telegram bot orqali bildirishnomalar yuborish ──────────
        bot = request.app.get('bot')
        if bot:
            class SimpleUser:
                def __init__(self, uid, name, username=None):
                    self.id = uid
                    self.full_name = name
                    self.username = username

            full_name = user_row['full_name'] if user_row else "Mijoz"
            username = user_row['username'] if user_row else None
            tg_user = SimpleUser(user_id, full_name, username)

            asyncio.create_task(notify_admins_new_order(
                bot=bot,
                order_id=order_id,
                total_amount=total_amount,
                user=tg_user,
                items=items,
                phone=phone,
                address=address,
                location={'lat': lat, 'lon': lon},
                note=None,
                delivery_type=delivery_type,
                payment_method=payment_method,
            ))

            receipt = "".join(
                get_text("item_line", lang, name=get_product_name(i, lang), qty=i['quantity'],
                         total=i['price'] * i['quantity']) + "\n"
                for i in items
            )

            discount_text = (get_text("promo_line", lang, code=promo_code, amt=discount_amt)
                             if discount_amt > 0 else "")

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
                markup = get_admin_main_menu(lang) if is_admin else get_user_main_menu(lang)
                
                await bot.send_message(
                    chat_id=user_id,
                    text=success_text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Mijozga bot orqali xabar yuborishda xato: {e}")

        return add_cors_headers(web.json_response({
            'success': True,
            'order_id': order_id,
            'total_amount': total_amount
        }))

    except Exception as e:
        logging.error(f"/api/order/create error: {e}", exc_info=True)
        return add_cors_headers(web.json_response({'error': str(e)}, status=500))


def register_webapp_api(app: web.Application):
    app.router.add_options('/api/user', options_handler)
    app.router.add_get('/api/user', api_user_profile)

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
