import logging
from aiohttp import web
import json
from config import ADMIN_ID
from database.crud import (
    get_user, get_user_orders, get_favorites, toggle_favorite,
    search_products, get_today_stats, get_all_orders, update_order_status,
    add_product, update_product_image, get_categories, get_products_by_category,
    delete_promo_code
)
from database.connection import get_db_pool

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
            return add_cors_headers(web.json_response({"error": "User not found"}, status=404))
            
        orders = await get_user_orders(user_id, limit=50)
        
        user_dict = dict(user)
        orders_list = []
        for o in orders:
            o_dict = dict(o)
            # Fetch order items
            async with pool.acquire() as conn:
                items = await conn.fetch("SELECT * FROM order_items WHERE order_id = $1", o_dict['id'])
                items_list = [dict(i) for i in items]
                o_dict['items'] = items_list
            orders_list.append(o_dict)
            
        return add_cors_headers(web.json_response({
            "user": {
                "id": user_dict['user_id'],
                "name": user_dict.get('full_name') or user_dict.get('username') or 'User',
                "phone": user_dict.get('phone_number') or '',
                "lang": user_dict.get('language') or 'uz',
                "is_admin": _is_admin(user_id)
            },
            "orders": orders_list
        }, default=str))
    except Exception as e:
        logging.error(f"/api/user error: {e}")
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

def register_webapp_api(app: web.Application):
    app.router.add_options('/api/user', options_handler)
    app.router.add_get('/api/user', api_user_profile)
    
    app.router.add_options('/api/favorites', options_handler)
    app.router.add_get('/api/favorites', api_favorites)
    
    app.router.add_options('/api/favorites/toggle', options_handler)
    app.router.add_post('/api/favorites/toggle', api_favorites_toggle)
    
    app.router.add_options('/api/search', options_handler)
    app.router.add_get('/api/search', api_search)
    
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
