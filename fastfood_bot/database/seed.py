from .connection import get_db_pool

async def seed_data():
    pool = await get_db_pool()

    # 1. Kategoriyalar
    categories = [
        (1,  "Burgerlar",       "🍔"),
        (2,  "Lavashlar",       "🌯"),
        (3,  "Pitsalar",        "🍕"),
        (4,  "Ichimliklar",     "🥤"),
        (5,  "Hot-doglar",      "🌭"),
        (6,  "Gazaklar",        "🍟"),
        (7,  "Donerlar",        "🥙"),
        (8,  "KFC (Tovuqlar)",  "🍗"),
        (9,  "Kombo to'plamlar","🎁"),
        (10, "Shirinliklar",    "🍰"),
    ]

    async with pool.acquire() as conn:
        for cat_id, name, emoji in categories:
            exists = await conn.fetchval("SELECT id FROM categories WHERE id = $1", cat_id)
            if not exists:
                await conn.execute(
                    "INSERT INTO categories (id, name, emoji) VALUES ($1, $2, $3)",
                    cat_id, name, emoji
                )

    # 2. Mahsulotlar
    products = [
        # ── Burgerlar (cat 1) ─────────────────────────────────────────────────
        (1,  1, "Classic Burger",     "Mol go'shti kotleti, bodring, pomidor, ketchup, mayonez.",         25000, "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500"),
        (2,  1, "Cheeseburger",       "Cheddar pishloq, mol go'shti, salat bargi, maxsus sous.",          28000, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500"),
        (3,  1, "Double Burger",      "Ikkita kotlet, ikki qavat pishloq, maxsus sous.",                  45000, "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=500"),
        (4,  1, "BBQ Burger",         "BBQ sousi, qovurilgan piyoz, mol go'shti, dudlangan pishloq.",     38000, "https://images.unsplash.com/photo-1553979459-d2229ba7433b?w=500"),
        (5,  1, "Chicken Burger",     "Qovurilgan tovuq go'shti, coleslaw, ranch sousi.",                 32000, "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=500"),

        # ── Lavashlar (cat 2) ──────────────────────────────────────────────────
        (6,  2, "Mol go'shtli Lavash", "Mol go'shti, chips, bodring, pomidor, mayonez, ketchup.",         30000, "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=500"),
        (7,  2, "Tovuqli Lavash",      "Tovuq go'shti, chips, yangi sabzavotlar, garmdori sousi.",         28000, "https://images.unsplash.com/photo-1529042410759-befb1204b465?w=500"),
        (8,  2, "Mini Lavash",         "Kichikroq porsiya, ammo to'yimli va mazali.",                      22000, "https://images.unsplash.com/photo-1561651823-34feb02250e4?w=500"),
        (9,  2, "XL Lavash",           "Katta porsiya mol go'shti lavash, ikki marta to'yimli.",           40000, "https://images.unsplash.com/photo-1640719028782-8230a2a4ada9?w=500"),

        # ── Pitsalar (cat 3) ───────────────────────────────────────────────────
        (10, 3, "Pepperoni",           "Klassik pepperoni, motsarella, tomat sousi.",                       65000, "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=500"),
        (11, 3, "Margarita",           "Pomidor, rayhon, motsarella pishloqi.",                             55000, "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=500"),
        (12, 3, "BBQ Chicken Pizza",   "Tovuq, BBQ sous, qizil piyoz, koriander.",                         70000, "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=500"),
        (13, 3, "Hawai Pizza",         "Jambon, ananas, pishloq, tomat sousi.",                            68000, "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=500"),
        (14, 3, "4 Pishloqli",         "Motsarella, cheddar, parmezan, gorgonzola.",                       72000, "https://images.unsplash.com/photo-1571407970349-bc81e7e96d47?w=500"),

        # ── Ichimliklar (cat 4) ────────────────────────────────────────────────
        (15, 4, "Coca Cola 0.5L",     "Muzdek Coca-Cola.",                                                 8000, "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500"),
        (16, 4, "Fanta 0.5L",         "Apelsin ta'mli gazli ichimlik.",                                   8000, "https://images.unsplash.com/photo-1624517452488-04869289c4ca?w=500"),
        (17, 4, "Sprite 0.5L",        "Limon-laym ta'mli muzdek ichimlik.",                               8000, "https://images.unsplash.com/photo-1625772452859-1c03d5bf1137?w=500"),
        (18, 4, "Apelsin Sharbat",    "Yangi siqilgan apelsin sharbati.",                                 12000, "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=500"),
        (19, 4, "Milkshake",          "Muzqaymoqli sut kokteyli — shokolad, vanil yoki qulupnay.",        18000, "https://images.unsplash.com/photo-1572490122747-3538f2e88eb1?w=500"),
        (20, 4, "Suv 0.5L",           "Gazsiz toza ichimlik suvi.",                                        3000, "https://images.unsplash.com/photo-1616118132534-381055979e47?w=500"),

        # ── Hot-doglar (cat 5) ─────────────────────────────────────────────────
        (21, 5, "Classic Hot-dog",    "Sosiska, ketchup, xantal, non ichida.",                             15000, "https://images.unsplash.com/photo-1612392062631-94bd4824a22c?w=500"),
        (22, 5, "Cheese Hot-dog",     "Sosiska, eritilgan pishloq, xantal, mayonez.",                      18000, "https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=500"),
        (23, 5, "XXL Hot-dog",        "Katta sosiska, ko'p sous, piyoz, bodring.",                         22000, "https://images.unsplash.com/photo-1591348278863-a8fb3887e2aa?w=500"),

        # ── Gazaklar (cat 6) ───────────────────────────────────────────────────
        (24, 6, "Kartoshka Fri",      "Qovurilgan kartoshka, ketchup yoki sous bilan.",                    12000, "https://images.unsplash.com/photo-1576777647209-e8733d7b851d?w=500"),
        (25, 6, "Nuggets (6 dona)",   "Tovuq nuggets, dippping sous bilan.",                               18000, "https://images.unsplash.com/photo-1562802378-063ec186a863?w=500"),
        (26, 6, "Mozzarella Sticks",  "Qovurilgan motsarella tayoqchalari, pomidor sousi bilan.",          20000, "https://images.unsplash.com/photo-1548340748-6d2b7d7da280?w=500"),
        (27, 6, "Ketchup sousi",      "Qo'shimcha ketchup sousi (100ml).",                                  3000, "https://images.unsplash.com/photo-1472476443507-c7369d1d7716?w=500"),

        # ── Donerlar (cat 7) ───────────────────────────────────────────────────
        (28, 7, "Toviuqli Doner",     "Grillda pishirilgan tovuq go'shti, sabzavot, yogurt sousi.",        32000, "https://images.unsplash.com/photo-1561651823-34feb02250e4?w=500"),
        (29, 7, "Mol go'shtli Doner", "Mol go'shti, lavash, pomidor, bodring, garmdori sousi.",            35000, "https://images.unsplash.com/photo-1545488454-9154e4f0c3dc?w=500"),
        (30, 7, "Mix Doner",          "Tovuq + mol go'shti aralash, barcha sous va sabzavotlar.",          40000, "https://images.unsplash.com/photo-1440133197387-5a6020d5ace2?w=500"),

        # ── KFC / Tovuqlar (cat 8) ─────────────────────────────────────────────
        (31, 8, "Qovurilgan Tovuq",   "KFC uslubida qovurilgan tovuq bo'lagi (2 dona).",                   28000, "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=500"),
        (32, 8, "Chicken Wings",      "Achchiq-chuchuk sousi bilan tovuq qanotlari (6 dona).",              30000, "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?w=500"),
        (33, 8, "Chicken Strips",     "Krustonli tovuq po'stloqli tasmalar, ranch sousi bilan.",            25000, "https://images.unsplash.com/photo-1562802378-063ec186a863?w=500"),
        (34, 8, "Spicy Chicken",      "Achchiq ziravorlarda marinlangan qovurilgan tovuq.",                 32000, "https://images.unsplash.com/photo-1598514982901-f62836411efa?w=500"),

        # ── Kombo to'plamlar (cat 9) ───────────────────────────────────────────
        (35, 9, "Burger Kombo",       "Classic Burger + Kartoshka Fri + Coca Cola 0.5L.",                  45000, "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?w=500"),
        (36, 9, "Oilaviy Kombo",      "2ta Burger + 2ta Kartoshka + 2ta Ichimlik.",                        85000, "https://images.unsplash.com/photo-1619881585-dc68d047f5fc?w=500"),
        (37, 9, "Pizza Kombo",        "Margarita Pitsa + 2ta Ichimlik.",                                   65000, "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=500"),
        (38, 9, "KFC Kombo",          "2ta Qovurilgan Tovuq + Kartoshka Fri + Sprite.",                    55000, "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?w=500"),

        # ── Shirinliklar (cat 10) ──────────────────────────────────────────────
        (39, 10, "Shokoladli Tort",   "Yumshoq shokoladli keks, krem bilan.",                              18000, "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=500"),
        (40, 10, "Cheesecake",        "Klassik limonli cheesecake, meva sousi bilan.",                     22000, "https://images.unsplash.com/photo-1533134242443-d4fd215305ad?w=500"),
        (41, 10, "Muzqaymoq",         "Vanil, shokolad yoki qulupnay — 2 sharli.",                         10000, "https://images.unsplash.com/photo-1501443762994-82bd5dace89a?w=500"),
        (42, 10, "Donut",             "Glazurli va sprinkalali donut.",                                    12000, "https://images.unsplash.com/photo-1551024601-bec78aea704b?w=500"),
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
