from .connection import get_db_pool

async def seed_data():
    pool = await get_db_pool()

    # 1. Kategoriyalar
    categories = [
        (1, "Burgerlar",    "🍔"),
        (2, "Lavashlar",    "🌯"),
        (3, "Pitsalar",     "🍕"),
        (4, "Salatlar",     "🥗"),
        (5, "Ichimliklar",  "🥤"),
        (6, "Desertlar",    "🍰"),
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
        # ── Burgerlar ──────────────────────────────────────────────────────────
        (1,  1, "Classic Burger",    "Mol go'shti kotleti, bodring, pomidor, ketchup, mayonez.",          25000, "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500"),
        (2,  1, "Cheeseburger",      "Eritilgan cheddar pishloq, mol go'shti, salat, sous.",              28000, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500"),
        (3,  1, "Double Burger",     "Ikkita kotlet, ikki qavat pishloq, maxsus sous.",                   45000, "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=500"),
        (4,  1, "BBQ Burger",        "BBQ sousi, qovurilgan piyoz, mol go'shti, dudlangan pishloq.",      38000, "https://images.unsplash.com/photo-1553979459-d2229ba7433b?w=500"),
        (5,  1, "Chicken Burger",    "Qovurilgan tovuq go'shti, coleslaw salat, ranch sousi.",            32000, "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=500"),
        (6,  1, "Veggie Burger",     "Sabzavotli kotlet, avokado, pomidor, salat bargi.",                 30000, "https://images.unsplash.com/photo-1585238342024-78d387f4a707?w=500"),

        # ── Lavashlar ──────────────────────────────────────────────────────────
        (7,  2, "Mol go'shtli Lavash","Mol go'shti, chips, bodring, pomidor, mayonez, ketchup.",          30000, "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=500"),
        (8,  2, "Tovuqli Lavash",    "Tovuq go'shti, chips, yangi sabzavotlar, garmdori sousi.",          28000, "https://images.unsplash.com/photo-1529042410759-befb1204b465?w=500"),
        (9,  2, "Mini Lavash",       "Kichikroq porsiya, ammo to'yimli va mazali.",                       22000, "https://images.unsplash.com/photo-1561651823-34feb02250e4?w=500"),
        (10, 2, "Shawarma Classic",  "Qo'zichoq go'shti, sabzavot, garmdori va suzma sousi.",             33000, "https://images.unsplash.com/photo-1545488454-9154e4f0c3dc?w=500"),
        (11, 2, "Falafel Lavash",    "Falafel, hummus, yangi sabzavotlar, tahini sousi.",                 27000, "https://images.unsplash.com/photo-1547592180-85f173990554?w=500"),
        (12, 2, "XL Lavash",         "Katta porsiya mol go'shti lavash, ikki marta to'yimli.",            40000, "https://images.unsplash.com/photo-1640719028782-8230a2a4ada9?w=500"),

        # ── Pitsalar ──────────────────────────────────────────────────────────
        (13, 3, "Pepperoni",         "Klassik pepperoni, motsarella, tomat sousi.",                       65000, "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=500"),
        (14, 3, "Margarita",         "Pomidor, rayhon, motsarella pishloqi.",                             55000, "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=500"),
        (15, 3, "BBQ Chicken Pizza", "Tovuq, BBQ sous, qizil piyoz, koriander.",                          70000, "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=500"),
        (16, 3, "Hawai Pizza",       "Jambon, ananas, pishloq, tomat sousi.",                             68000, "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=500"),
        (17, 3, "4 Pishloq",         "To'rt xil pishloq: motsarella, cheddar, parmezan, gorgonzola.",    72000, "https://images.unsplash.com/photo-1571407970349-bc81e7e96d47?w=500"),
        (18, 3, "Seafood Pizza",     "Krevetka, kalamar, tomat sousi, pishloq.",                          78000, "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=500"),

        # ── Salatlar ──────────────────────────────────────────────────────────
        (19, 4, "Cezar Salat",       "Romaine salat, krouton, parmezan, Cezar sousi.",                    22000, "https://images.unsplash.com/photo-1546793665-c74683f339c1?w=500"),
        (20, 4, "Tovuqli Cezar",     "Grillda pishirilgan tovuq bilan Cezar salat.",                      28000, "https://images.unsplash.com/photo-1550304943-4f24f54ddde9?w=500"),
        (21, 4, "Grek Salat",        "Pomidor, bodring, zaytun, feta pishloq, zaytun moyi.",              20000, "https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?w=500"),
        (22, 4, "Koleslo",           "Karam, sabzi, mayonez sousi — burger uchun ideal yon taoml.",       12000, "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=500"),
        (23, 4, "Vinegret",          "Lavlagi, kartoshka, havuç, karam, o'tkir marinad.",                 15000, "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=500"),

        # ── Ichimliklar ───────────────────────────────────────────────────────
        (24, 5, "Coca Cola 0.5L",    "Muzdek Coca-Cola.",                                                  8000, "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500"),
        (25, 5, "Fanta 0.5L",        "Apelsin ta'mli gazli ichimlik.",                                    8000, "https://images.unsplash.com/photo-1624517452488-04869289c4ca?w=500"),
        (26, 5, "Sprite 0.5L",       "Limon-laym ta'mli muzdek ichimlik.",                                8000, "https://images.unsplash.com/photo-1625772452859-1c03d5bf1137?w=500"),
        (27, 5, "Apelsin Sharbat",   "Yangi siqilgan apelsin sharbati.",                                  12000, "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=500"),
        (28, 5, "Milkshake",         "Muzqaymoqli sut kokteylli — shokolad, vanil yoki qulupnay.",        18000, "https://images.unsplash.com/photo-1572490122747-3538f2e88eb1?w=500"),
        (29, 5, "Choy (issiq)",      "Ko'k yoki qora choy, shakar bilan.",                               5000, "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=500"),
        (30, 5, "Suv 0.5L",          "Gazsiz toza ichimlik suvi.",                                        3000, "https://officemax.uz/media/uploads/cg0sh2fhgiov1qidgqm0.jpg"),

        # ── Desertlar ─────────────────────────────────────────────────────────
        (31, 6, "Shokoladli Tort",   "Yumshoq shokoladli keks, krem bilan.",                             18000, "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=500"),
        (32, 6, "Cheesecake",        "Klassik limonli cheesecake, meva sousi bilan.",                    22000, "https://images.unsplash.com/photo-1533134242443-d4fd215305ad?w=500"),
        (33, 6, "Muzqaymoq",         "Vanil, shokolad yoki qulupnay — 2 sharli.",                       10000, "https://images.unsplash.com/photo-1501443762994-82bd5dace89a?w=500"),
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
