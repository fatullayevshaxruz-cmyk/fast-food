from datetime import date
from .connection import get_db_pool
from .models import ALL_TABLES

async def init_database():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        for table_sql in ALL_TABLES:
            await conn.execute(table_sql)
        # Yangi ustunlar qo'shish (mavjud bo'lsa xato chiqadi — ignore)
        for alter in [
            "ALTER TABLE products ADD COLUMN old_price INTEGER",
            "ALTER TABLE orders ADD COLUMN note TEXT",
            "ALTER TABLE orders ADD COLUMN delivery_type VARCHAR(20) DEFAULT 'delivery'",
            "ALTER TABLE users ADD COLUMN default_address TEXT",
            "ALTER TABLE users ADD COLUMN language VARCHAR(10) DEFAULT 'uz'",
            # Ko'p tilli nom va tavsif ustunlari
            "ALTER TABLE products ADD COLUMN name_ru TEXT",
            "ALTER TABLE products ADD COLUMN name_en TEXT",
            "ALTER TABLE products ADD COLUMN description_ru TEXT",
            "ALTER TABLE products ADD COLUMN description_en TEXT",
        ]:
            try:
                await conn.execute(alter)
            except Exception:
                pass

async def create_user(user_id, username, full_name):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # PostgreSQL: ON CONFLICT, SQLite: INSERT OR REPLACE
        try:
            await conn.execute("""
                INSERT INTO users (user_id, username, full_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE 
                SET username = EXCLUDED.username, full_name = EXCLUDED.full_name
            """, user_id, username, full_name)
        except Exception:
            # SQLite fallback
            existing = await conn.fetchrow("SELECT user_id FROM users WHERE user_id = $1", user_id)
            if existing:
                await conn.execute(
                    "UPDATE users SET username = $1, full_name = $2 WHERE user_id = $3",
                    username, full_name, user_id
                )
            else:
                await conn.execute(
                    "INSERT INTO users (user_id, username, full_name) VALUES ($1, $2, $3)",
                    user_id, username, full_name
                )

async def get_user(user_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def update_user_phone(user_id, phone_number):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET phone_number = $1 WHERE user_id = $2", phone_number, user_id)

async def get_user_language(user_id) -> str:
    """Foydalanuvchi tilini DB dan olish. Default: 'uz'."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        lang = await conn.fetchval(
            "SELECT language FROM users WHERE user_id = $1", user_id
        )
        return lang or "uz"

async def set_user_language(user_id, lang: str):
    """Foydalanuvchi tilini DB ga saqlash."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET language = $1 WHERE user_id = $2", lang, user_id
        )

# ── Kesh (tezlashtirish uchun) ───────────────────────────────────────
import time

_cache = {}
_CACHE_TTL = 60  # 60 soniya — keyin yangilanadi

def _get_cached(key):
    """Keshdan olish. Muddati o'tgan bo'lsa None qaytaradi."""
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
    return None

def _set_cache(key, data):
    _cache[key] = (data, time.time())

def clear_cache(prefix=None):
    """Keshni tozalash (admin o'zgarish qilganda)."""
    if prefix:
        keys = [k for k in _cache if k.startswith(prefix)]
        for k in keys:
            del _cache[k]
    else:
        _cache.clear()


async def get_categories():
    cached = _get_cached("categories")
    if cached is not None:
        return cached
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.fetch("SELECT * FROM categories ORDER BY id")
        _set_cache("categories", result)
        return result

async def get_products_by_category(category_id):
    key = f"products_cat_{category_id}"
    cached = _get_cached(key)
    if cached is not None:
        return cached
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # is_active TRUE ham 1 ham TRUE qabul qiladi (PostgreSQL va SQLite)
        result = await conn.fetch(
            "SELECT * FROM products WHERE category_id = $1 AND is_active != 0 AND is_active != 'false'",
            int(category_id)
        )
        _set_cache(key, result)
        return result

async def get_product(product_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM products WHERE id = $1", int(product_id))

async def add_to_cart(user_id, product_id, quantity=1):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT quantity FROM cart_items WHERE user_id = $1 AND product_id = $2", user_id, int(product_id))
        if row:
            await conn.execute("UPDATE cart_items SET quantity = quantity + $1 WHERE user_id = $2 AND product_id = $3", quantity, user_id, int(product_id))
        else:
            await conn.execute("INSERT INTO cart_items (user_id, product_id, quantity) VALUES ($1, $2, $3)", user_id, int(product_id), quantity)

async def get_cart_items(user_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT c.*, p.name, p.price, p.image_url 
            FROM cart_items c 
            JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = $1
        """, user_id)

async def clear_cart(user_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM cart_items WHERE user_id = $1", user_id)

async def remove_from_cart(cart_item_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM cart_items WHERE id = $1", int(cart_item_id))

async def create_order(user_id, total_amount, address, payment_method,
                       latitude=None, longitude=None, phone_number=None,
                       note=None, delivery_type="delivery"):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO orders (user_id, total_amount, delivery_address, payment_method,
                                latitude, longitude, phone_number, note, delivery_type)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """, user_id, total_amount, address, payment_method,
             latitude, longitude, phone_number, note, delivery_type)
        return row['id']

async def add_order_items(order_id, cart_items):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for item in cart_items:
                await conn.execute("""
                    INSERT INTO order_items (order_id, product_id, quantity, price_at_time)
                    VALUES ($1, $2, $3, $4)
                """, order_id, item['product_id'], item['quantity'], item['price'])

async def add_product(category_id: int, name: str, price: int, description: str = "",
                      image_url: str = None,
                      name_ru: str = None, name_en: str = None,
                      description_ru: str = None, description_en: str = None) -> int:
    """Yangi mahsulot qo'shadi. Ko'p tilli nom va tavsif ixtiyoriy."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Avval ko'p tilli ustunlar bilan urinib ko'rish
        try:
            row = await conn.fetchrow("""
                INSERT INTO products
                  (category_id, name, description, price, image_url, is_active,
                   name_ru, name_en, description_ru, description_en)
                VALUES ($1, $2, $3, $4, $5, 1, $6, $7, $8, $9)
                RETURNING id
            """, category_id, name, description, price, image_url,
                 name_ru or None, name_en or None,
                 description_ru or None, description_en or None)
        except Exception:
            # Eski ustunlar bilan fallback (migration hali ishlamagan)
            row = await conn.fetchrow("""
                INSERT INTO products (category_id, name, description, price, image_url, is_active)
                VALUES ($1, $2, $3, $4, $5, 1)
                RETURNING id
            """, category_id, name, description, price, image_url)
        clear_cache("products_cat_")
        return row['id']


def get_product_name(product, lang: str) -> str:
    """Mahsulot nomini tanlangan tilda qaytaradi. Xato bo'lsa o'zbekcha."""
    try:
        if lang == "ru":
            return _field(product, 'name_ru') or product['name']
        if lang == "en":
            return _field(product, 'name_en') or product['name']
    except Exception:
        pass
    return product['name']


def get_product_desc(product, lang: str) -> str:
    """Mahsulot tavsifini tanlangan tilda qaytaradi. Xato bo'lsa o'zbekcha."""
    try:
        if lang == "ru":
            return _field(product, 'description_ru') or _field(product, 'description') or ""
        if lang == "en":
            return _field(product, 'description_en') or _field(product, 'description') or ""
        return _field(product, 'description') or ""
    except Exception:
        pass
    try:
        return product.get('description') or ""
    except Exception:
        return ""


def _field(record, key):
    """asyncpg Record yoki dict dan xavfsiz maydon olish — har qanday xatoni tutadi."""
    try:
        if isinstance(record, dict):
            return record.get(key)
        return record[key]
    except Exception:
        return None

async def get_user_orders(user_id, limit=10):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM orders 
            WHERE user_id = $1 
            ORDER BY created_at DESC 
            LIMIT $2
        """, user_id, limit)

# ── Yangi CRUD funksiyalar ──────────────────────────────────────────

async def get_all_orders(status=None, limit=20):
    """Admin uchun barcha buyurtmalar."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if status:
            return await conn.fetch(
                "SELECT o.*, u.full_name, u.username FROM orders o LEFT JOIN users u ON o.user_id = u.user_id WHERE o.status = $1 ORDER BY o.created_at DESC LIMIT $2",
                status, limit
            )
        return await conn.fetch(
            "SELECT o.*, u.full_name, u.username FROM orders o LEFT JOIN users u ON o.user_id = u.user_id ORDER BY o.created_at DESC LIMIT $1",
            limit
        )

async def get_order_by_id(order_id):
    """Bitta buyurtma tafsiloti."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT o.*, u.full_name, u.username FROM orders o LEFT JOIN users u ON o.user_id = u.user_id WHERE o.id = $1",
            int(order_id)
        )

async def get_order_items_detail(order_id):
    """Buyurtma ichidagi mahsulotlar."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT oi.*, p.name 
            FROM order_items oi 
            JOIN products p ON oi.product_id = p.id 
            WHERE oi.order_id = $1
        """, int(order_id))

async def update_order_status(order_id, status):
    """Buyurtma holatini yangilash."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status = $1 WHERE id = $2",
            status, int(order_id)
        )

async def toggle_product_active(product_id):
    """Mahsulotni yashirish/ko'rsatish."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow("SELECT is_active, category_id FROM products WHERE id = $1", int(product_id))
        if product:
            new_status = not product['is_active']
            await conn.execute("UPDATE products SET is_active = $1 WHERE id = $2", new_status, int(product_id))
            clear_cache("products_cat_")
            return new_status
    return None

async def search_products(query):
    """Mahsulot izlash (case-insensitive)."""
    pool = await get_db_pool()
    search = f"%{query.lower()}%"
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE LOWER(p.name) LIKE $1 AND p.is_active != 0 LIMIT 10",
            search
        )

async def update_product_image(product_id, image_url):
    """Mahsulot rasmini yangilash."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE products SET image_url = $1 WHERE id = $2", image_url, int(product_id))
    clear_cache("products_cat_")

async def set_product_discount(product_id, new_price):
    """Chegirma qo'yish — eski narxni old_price ga saqlaydi."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow("SELECT price FROM products WHERE id = $1", int(product_id))
        if product:
            await conn.execute(
                "UPDATE products SET old_price = $1, price = $2 WHERE id = $3",
                product['price'], new_price, int(product_id)
            )
    clear_cache("products_cat_")

async def remove_product_discount(product_id):
    """Chegirmani olib tashlash."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow("SELECT old_price FROM products WHERE id = $1", int(product_id))
        if product and product['old_price']:
            await conn.execute(
                "UPDATE products SET price = $1, old_price = $2 WHERE id = $3",
                product['old_price'], None, int(product_id)
            )

async def get_today_stats():
    """Bugungi statistika."""
    pool = await get_db_pool()
    today_str = date.today().isoformat()
    async with pool.acquire() as conn:
        today_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE created_at >= $1", today_str
        )
        today_revenue = await conn.fetchval(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE created_at >= $1", today_str
        )
        return today_orders or 0, today_revenue or 0

async def get_top_products(limit=5):
    """Eng ko'p sotilgan mahsulotlar."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT p.name, SUM(oi.quantity) as total_qty
            FROM order_items oi 
            JOIN products p ON oi.product_id = p.id 
            GROUP BY p.name 
            ORDER BY total_qty DESC 
            LIMIT $1
        """, limit)

async def get_all_products_admin():
    """Admin uchun barcha mahsulotlar (yashirilganlar ham)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT p.*, c.name as category_name FROM products p JOIN categories c ON p.category_id = c.id ORDER BY p.id")

# ── Sevimlilar ───────────────────────────────────────────────────────

async def toggle_favorite(user_id, product_id):
    """Sevimli qo'shish/olib tashlash. True=qo'shildi, False=olib tashlandi."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT id FROM favorites WHERE user_id = $1 AND product_id = $2",
            user_id, int(product_id)
        )
        if exists:
            await conn.execute("DELETE FROM favorites WHERE user_id = $1 AND product_id = $2", user_id, int(product_id))
            return False
        else:
            await conn.execute("INSERT INTO favorites (user_id, product_id) VALUES ($1, $2)", user_id, int(product_id))
            return True

async def is_favorite(user_id, product_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchval("SELECT id FROM favorites WHERE user_id = $1 AND product_id = $2", user_id, int(product_id))
        return r is not None

async def get_favorites(user_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT p.*, c.name as category_name FROM favorites f JOIN products p ON f.product_id = p.id LEFT JOIN categories c ON p.category_id = c.id WHERE f.user_id = $1 AND p.is_active != 0 ORDER BY f.created_at DESC",
            user_id
        )

# ── Promo kodlar ─────────────────────────────────────────────────────

async def create_promo_code(code, discount_percent, max_uses=0, min_order_amount=0):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO promo_codes (code, discount_percent, max_uses, min_order_amount) VALUES ($1, $2, $3, $4)",
            code.upper(), discount_percent, max_uses, min_order_amount
        )

async def get_promo_code(code):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM promo_codes WHERE code = $1 AND is_active = TRUE", code.upper())

async def check_user_promo_used(user_id, code):
    """Foydalanuvchi bu promo kodni avval ishlatganmi?"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchval(
            "SELECT COUNT(*) FROM promo_code_uses WHERE user_id = $1 AND promo_code = $2",
            user_id, code.upper()
        )
        return (r or 0) > 0

async def use_promo_code(code, user_id=None):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = $1", code.upper())
        if user_id:
            await conn.execute(
                "INSERT INTO promo_code_uses (user_id, promo_code) VALUES ($1, $2)",
                user_id, code.upper()
            )

async def get_all_promo_codes():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM promo_codes ORDER BY created_at DESC")

async def delete_promo_code(code):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM promo_codes WHERE code = $1", code.upper())

# ── Profil ───────────────────────────────────────────────────────────

async def update_user_name(user_id, name):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET full_name = $1 WHERE user_id = $2", name, user_id)

async def update_user_phone(user_id, phone):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET phone_number = $1 WHERE user_id = $2", phone, user_id)

async def update_user_address(user_id, address):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET default_address = $1 WHERE user_id = $2", address, user_id)

async def get_user_address(user_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT default_address FROM users WHERE user_id = $1", user_id)

# ── Takroriy buyurtma ────────────────────────────────────────────────

async def repeat_order_to_cart(user_id, order_id):
    """Buyurtmadagi mahsulotlarni savatga qo'shish."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        items = await conn.fetch("SELECT product_id, quantity FROM order_items WHERE order_id = $1", int(order_id))
        for item in items:
            existing = await conn.fetchrow(
                "SELECT quantity FROM cart_items WHERE user_id = $1 AND product_id = $2",
                user_id, item['product_id']
            )
            if existing:
                await conn.execute(
                    "UPDATE cart_items SET quantity = quantity + $1 WHERE user_id = $2 AND product_id = $3",
                    item['quantity'], user_id, item['product_id']
                )
            else:
                await conn.execute(
                    "INSERT INTO cart_items (user_id, product_id, quantity) VALUES ($1, $2, $3)",
                    user_id, item['product_id'], item['quantity']
                )
        return len(items)

# ── CSV eksport ──────────────────────────────────────────────────────

async def get_orders_for_export():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT o.id, u.full_name, u.phone_number as user_phone, o.total_amount,
                   o.delivery_address, o.phone_number as order_phone,
                   o.delivery_type, o.note, o.status, o.created_at
            FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
            ORDER BY o.created_at DESC
        """)
