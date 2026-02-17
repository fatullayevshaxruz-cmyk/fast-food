from .connection import get_db_pool
from .models import ALL_TABLES

async def init_database():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        for table_sql in ALL_TABLES:
            await conn.execute(table_sql)

async def create_user(user_id, username, full_name):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE 
            SET username = EXCLUDED.username, full_name = EXCLUDED.full_name
        """, user_id, username, full_name)

async def get_user(user_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def get_categories():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM categories ORDER BY id")

async def get_products_by_category(category_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM products WHERE category_id = $1 AND is_active = TRUE", int(category_id))

async def get_product(product_id):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM products WHERE id = $1", int(product_id))

async def add_to_cart(user_id, product_id, quantity=1):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if item exists
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

async def create_order(user_id, total_amount, address, payment_method, latitude=None, longitude=None, phone_number=None):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO orders (user_id, total_amount, delivery_address, payment_method, latitude, longitude, phone_number)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """, user_id, total_amount, address, payment_method, latitude, longitude, phone_number)
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

async def get_user_orders(user_id, limit=5):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM orders 
            WHERE user_id = $1 
            ORDER BY created_at DESC 
            LIMIT $2
        """, user_id, limit)


