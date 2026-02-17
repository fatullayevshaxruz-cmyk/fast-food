from .connection import get_db_pool

async def seed_data():
    pool = await get_db_pool()
    
    # 1. Categories
    categories = [
        (1, "Burgerlar", "🍔"),
        (2, "Lavashlar", "🌯"),
        (3, "Pitsalar", "🍕"),
        (4, "Ichimliklar", "🥤"),
    ]
    
    async with pool.acquire() as conn:
        for cat_id, name, emoji in categories:
            # Check if exists (simple check by ID or name)
            exists = await conn.fetchval("SELECT id FROM categories WHERE id = $1", cat_id)
            if not exists:
                await conn.execute(
                    "INSERT INTO categories (id, name, emoji) VALUES ($1, $2, $3)", 
                    cat_id, name, emoji
                )
    
    # 2. Products
    products = [
        # Burgers
        (1, 1, "Gamburger", "Klassik mol go'shti kotleti, bodring, pomidor, sous.", 25000, "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500"),
        (2, 1, "Chizburger", "Eritilgan pishloq, mol go'shti, salat bargi.", 28000, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500"),
        (3, 1, "Double Burger", "Ikkita kotlet, ikki qavat pishloq, maxsus sous.", 45000, "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=500"),
        
        # Lavash
        (4, 2, "Mol go'shtli Lavash", "Mol go'shti, chips, bodring, pomidor, mayonez, ketchup.", 30000, "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=500"),
        (5, 2, "Tovuqli Lavash", "Tovuq go'shti, chips, yangi sabzavotlar.", 28000, "https://images.unsplash.com/photo-1529042410759-befb1204b465?w=500"),
        (6, 2, "Mini Lavash", "Kichikroq porsiya, ammo to'yimli.", 22000, "https://images.unsplash.com/photo-1561651823-34feb02250e4?w=500"),    

        # Pitsa
        (7, 3, "Pepperoni", "Klassik pepperoni kolbasasi, motsarella, tomat sousi.", 65000, "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=500"),
        (8, 3, "Margarita", "Pomidor, rayhon, motsarella pishloqi.", 55000, "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=500"),
        
        # Ichimliklar
        (9, 4, "Coca Cola 0.5L", "Muzdek Coca Cola.", 8000, "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500"),
        (10, 4, "Fanta 0.5L", "Apelsin ta'mli gazli ichimlik.", 8000, "https://images.unsplash.com/photo-1624517452488-04869289c4ca?w=500"),
        (11, 4, "Suv 0.5L", "Gazsiz ichimlik suvi.", 3000, "https://images.unsplash.com/photo-1564419320461-6870880221ad?w=500"),
    ]

    async with pool.acquire() as conn:
        for pid, cat_id, name, desc, price, img in products:
            exists = await conn.fetchval("SELECT id FROM products WHERE id = $1", pid)
            if not exists:
                await conn.execute(
                    """
                    INSERT INTO products (id, category_id, name, description, price, image_url, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                    """,
                    pid, cat_id, name, desc, price, img
                )
