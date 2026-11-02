from .connection import get_db_pool

async def seed_data():
    """Darxan Burger restoran menyusini bazaga kiritish."""
    pool = await get_db_pool()

    # ── Avval eski menyu ma'lumotlarni tozalash ──────────────────────
    async with pool.acquire() as conn:
        # Bog'liq jadvallarni avval tozalash
        try:
            await conn.execute("DELETE FROM cart_items")
        except Exception:
            pass
        try:
            await conn.execute("DELETE FROM order_items")
        except Exception:
            pass
        try:
            await conn.execute("DELETE FROM favorites")
        except Exception:
            pass
        await conn.execute("DELETE FROM products")
        await conn.execute("DELETE FROM categories")

    # ── Darxan Burger kategoriyalari ─────────────────────────────────
    categories = [
        (1, "Burgerlar",        "🍔", "Бургеры",          "Burgers"),
        (2, "Lavash & Doner",   "🌯", "Лаваш и Донер",   "Wrap & Doner"),
        (3, "Ichimliklar",      "🥤", "Напитки",          "Drinks"),
        (4, "Gazaklar",         "🍟", "Закуски",          "Snacks"),
        (5, "Kombo to'plamlar", "🎁", "Комбо наборы",     "Combo Sets"),
    ]

    async with pool.acquire() as conn:
        for cat_id, name, emoji, name_ru, name_en in categories:
            try:
                await conn.execute(
                    "INSERT INTO categories (id, name, emoji, name_ru, name_en) VALUES ($1, $2, $3, $4, $5)",
                    cat_id, name, emoji, name_ru, name_en
                )
            except Exception:
                try:
                    await conn.execute(
                        "INSERT INTO categories (id, name, emoji) VALUES ($1, $2, $3)",
                        cat_id, name, emoji
                    )
                except Exception:
                    pass
            # Tarjimalarni yangilash
            try:
                await conn.execute(
                    "UPDATE categories SET name_ru = $1, name_en = $2 WHERE id = $3",
                    name_ru, name_en, cat_id
                )
            except Exception:
                pass

    # ── Darxan Burger mahsulotlari ───────────────────────────────────
    products = [
        # ── Burgerlar (cat 1) ────────────────────────────────────────
        (1, 1, "Darxan Cheese Burger",
         "Shirali mol go'shti kotleti, pishloq, salat bargi, pomidor, maxsus sous.",
         "Дархан Чизбургер", "Сочная говяжья котлета, сыр, лист салата, помидор, фирменный соус.",
         "Darxan Cheese Burger", "Juicy beef patty, cheese, lettuce, tomato, special sauce.",
         38000, "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600"),

        (2, 1, "Double Cheese Burger",
         "Ikkita mol go'shti kotleti, ikki qavat pishloq, maxsus sous.",
         "Двойной Чизбургер", "Две говяжьи котлеты, два слоя сыра, фирменный соус.",
         "Double Cheese Burger", "Two beef patties, double cheese, special sauce.",
         48000, "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=600"),

        (3, 1, "Darxan Big Burger",
         "Katta porsiya mol go'shti, pishloq, achchiq sous, qovurilgan piyoz.",
         "Дархан Биг Бургер", "Большая порция говядины, сыр, острый соус, жареный лук.",
         "Darxan Big Burger", "Large beef portion, cheese, spicy sauce, fried onions.",
         55000, "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=600"),

        (4, 1, "Chicken Burger",
         "Qovurilgan tovuq filesi, salat, pomidor, mayonez.",
         "Чикен Бургер", "Жареное куриное филе, салат, помидор, майонез.",
         "Chicken Burger", "Fried chicken fillet, lettuce, tomato, mayo.",
         35000, "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=600"),

        (5, 1, "BBQ Burger",
         "BBQ sousi, dudlangan pishloq, mol go'shti, qovurilgan piyoz.",
         "BBQ Бургер", "Соус BBQ, копчёный сыр, говядина, жареный лук.",
         "BBQ Burger", "BBQ sauce, smoked cheese, beef, fried onions.",
         42000, "https://images.unsplash.com/photo-1553979459-d2229ba7433b?w=600"),

        (6, 1, "Darxan Kids Burger",
         "Bolalar uchun kichik burger — kotlet, pishloq, ketchup.",
         "Дархан Детский Бургер", "Маленький бургер для детей — котлета, сыр, кетчуп.",
         "Darxan Kids Burger", "Small burger for kids — patty, cheese, ketchup.",
         25000, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=600"),

        # ── Lavash & Doner (cat 2) ───────────────────────────────────
        (7, 2, "Mol go'shtli Lavash",
         "Tandir mol go'shti, chips, bodring, pomidor, sous.",
         "Лаваш с говядиной", "Тандырная говядина, чипсы, огурец, помидор, соус.",
         "Beef Wrap", "Tandoori beef, chips, cucumber, tomato, sauce.",
         35000, "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=600"),

        (8, 2, "Tovuqli Lavash",
         "Tovuq go'shti, chips, sabzavotlar, garmdori sousi.",
         "Лаваш с курицей", "Курица, чипсы, овощи, чесночный соус.",
         "Chicken Wrap", "Chicken, chips, fresh veggies, garlic sauce.",
         32000, "https://images.unsplash.com/photo-1600891964092-4316c288032e?w=600"),

        (9, 2, "XL Lavash",
         "Katta porsiya mol go'shti lavash, ikki marta to'yimli.",
         "XL Лаваш", "Большая порция лаваша с говядиной, двойная сытность.",
         "XL Wrap", "Extra large beef wrap, twice as filling.",
         45000, "https://images.unsplash.com/photo-1585238341710-4d3ff484184d?w=600"),

        (10, 2, "Tovuqli Doner",
         "Grillda pishirilgan tovuq, sabzavotlar, yogurt sousi.",
         "Донер с курицей", "Курица на гриле, овощи, йогуртовый соус.",
         "Chicken Doner", "Grilled chicken, vegetables, yogurt sauce.",
         33000, "https://images.unsplash.com/photo-1530469912745-a215c6b256ea?w=600"),

        (11, 2, "Mol go'shtli Doner",
         "Mol go'shti, lavash, pomidor, bodring, garmdori sousi.",
         "Донер с говядиной", "Говядина, лаваш, помидор, огурец, чесночный соус.",
         "Beef Doner", "Beef, flatbread, tomato, cucumber, garlic sauce.",
         38000, "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=600"),

        (12, 2, "Mix Doner",
         "Tovuq + mol go'shti aralash, barcha sous va sabzavotlar.",
         "Микс Донер", "Курица + говядина, все соусы и овощи.",
         "Mix Doner", "Chicken + beef mix, all sauces and vegetables.",
         42000, "https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=600"),

        # ── Ichimliklar (cat 3) ──────────────────────────────────────
        (13, 3, "Coca Cola 0.5L",
         "Muzdek Coca-Cola.",
         "Кока-Кола 0.5Л", "Охлаждённая Кока-Кола.",
         "Coca Cola 0.5L", "Ice cold Coca-Cola.",
         8000, "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=600"),

        (14, 3, "Fanta 0.5L",
         "Apelsin ta'mli gazli ichimlik.",
         "Фанта 0.5Л", "Газированный напиток со вкусом апельсина.",
         "Fanta 0.5L", "Orange flavored carbonated drink.",
         8000, "https://images.unsplash.com/photo-1624517452488-04869289c4ca?w=600"),

        (15, 3, "Sprite 0.5L",
         "Limon-laym ta'mli muzdek ichimlik.",
         "Спрайт 0.5Л", "Охлаждённый напиток со вкусом лимона и лайма.",
         "Sprite 0.5L", "Lemon-lime flavored cold drink.",
         8000, "https://images.unsplash.com/photo-1625772452859-1c03d5bf1137?w=600"),

        (16, 3, "Suv 0.5L",
         "Gazsiz toza ichimlik suvi.",
         "Вода 0.5Л", "Негазированная чистая питьевая вода.",
         "Water 0.5L", "Still clean drinking water.",
         3000, "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=600"),

        (17, 3, "Choy",
         "Issiq ko'k yoki qora choy.",
         "Чай", "Горячий зелёный или чёрный чай.",
         "Tea", "Hot green or black tea.",
         5000, "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=600"),

        # ── Gazaklar (cat 4) ─────────────────────────────────────────
        (18, 4, "Kartoshka Fri",
         "Qovurilgan kartoshka, ketchup yoki sous bilan.",
         "Картошка фри", "Жареный картофель с кетчупом или соусом.",
         "French Fries", "Fried potatoes with ketchup or sauce.",
         12000, "https://images.unsplash.com/photo-1630384060421-cb20d0e0649d?w=600"),

        (19, 4, "Nuggets (6 dona)",
         "Tovuq nuggets, dipping sous bilan.",
         "Наггетсы (6 шт.)", "Куриные наггетсы с соусом для обмакивания.",
         "Nuggets (6 pcs)", "Chicken nuggets with dipping sauce.",
         18000, "https://images.unsplash.com/photo-1562802378-063ec186a863?w=600"),

        (20, 4, "Qo'shimcha sous",
         "Ketchup, mayonez yoki garmdori sousi (100ml).",
         "Дополнительный соус", "Кетчуп, майонез или чесночный соус (100мл).",
         "Extra Sauce", "Ketchup, mayo or garlic sauce (100ml).",
         3000, "https://images.unsplash.com/photo-1461009683693-342af2f2d6ce?w=600"),

        # ── Kombo to'plamlar (cat 5) ─────────────────────────────────
        (21, 5, "Darxan Kombo",
         "Darxan Cheese Burger + Kartoshka Fri + Coca Cola 0.5L.",
         "Дархан Комбо", "Дархан Чизбургер + Картошка фри + Кока-Кола 0.5Л.",
         "Darxan Combo", "Darxan Cheese Burger + French Fries + Coca Cola 0.5L.",
         52000, "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?w=600"),

        (22, 5, "Double Kombo",
         "Double Cheese Burger + Kartoshka Fri + Fanta 0.5L.",
         "Двойное Комбо", "Двойной Чизбургер + Картошка фри + Фанта 0.5Л.",
         "Double Combo", "Double Cheese Burger + French Fries + Fanta 0.5L.",
         62000, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=600"),

        (23, 5, "Oilaviy Kombo",
         "2ta Darxan Burger + 2ta Kartoshka Fri + 2ta Ichimlik.",
         "Семейное Комбо", "2 бургера Дархан + 2 картошки фри + 2 напитка.",
         "Family Combo", "2 Darxan Burgers + 2 Fries + 2 Drinks.",
         95000, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=600"),
    ]

    async with pool.acquire() as conn:
        for pid, cat_id, name, desc, name_ru, desc_ru, name_en, desc_en, price, img in products:
            try:
                await conn.execute(
                    """
                    INSERT INTO products (id, category_id, name, description, price, image_url, is_active,
                                          name_ru, name_en, description_ru, description_en)
                    VALUES ($1, $2, $3, $4, $5, $6, TRUE, $7, $8, $9, $10)
                    """,
                    pid, cat_id, name, desc, price, img,
                    name_ru, name_en, desc_ru, desc_en
                )
            except Exception:
                try:
                    await conn.execute(
                        """
                        INSERT INTO products (id, category_id, name, description, price, image_url, is_active)
                        VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                        """,
                        pid, cat_id, name, desc, price, img
                    )
                except Exception:
                    pass
