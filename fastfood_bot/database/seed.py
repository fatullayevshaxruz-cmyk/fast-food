from .connection import get_db_pool

async def seed_data():
    pool = await get_db_pool()

    # 1. Kategoriyalar (UZ nomi + RU/EN tarjimalari)
    categories = [
        (1,  "Burgerlar",        "🍔", "Бургеры",           "Burgers"),
        (2,  "Lavashlar",        "🌯", "Лаваши",            "Wraps"),
        (3,  "Pitsalar",         "🍕", "Пиццы",             "Pizzas"),
        (4,  "Ichimliklar",      "🥤", "Напитки",           "Drinks"),
        (5,  "Hot-doglar",       "🌭", "Хот-доги",          "Hot Dogs"),
        (6,  "Gazaklar",         "🍟", "Закуски",           "Snacks"),
        (7,  "Donerlar",         "🥙", "Донеры",            "Doners"),
        (8,  "KFC (Tovuqlar)",   "🍗", "KFC (Курица)",      "KFC (Chicken)"),
        (9,  "Kombo to'plamlar", "🎁", "Комбо наборы",      "Combo Sets"),
        (10, "Shirinliklar",     "🍰", "Десерты",           "Desserts"),
    ]

    async with pool.acquire() as conn:
        for cat_id, name, emoji, name_ru, name_en in categories:
            exists = await conn.fetchval("SELECT id FROM categories WHERE id = $1", cat_id)
            if not exists:
                try:
                    await conn.execute(
                        "INSERT INTO categories (id, name, emoji, name_ru, name_en) VALUES ($1, $2, $3, $4, $5)",
                        cat_id, name, emoji, name_ru, name_en
                    )
                except Exception:
                    await conn.execute(
                        "INSERT INTO categories (id, name, emoji) VALUES ($1, $2, $3)",
                        cat_id, name, emoji
                    )
            # Mavjud kategoriyalarga tarjima qo'shish
            try:
                await conn.execute(
                    "UPDATE categories SET name_ru = $1, name_en = $2 WHERE id = $3",
                    name_ru, name_en, cat_id
                )
            except Exception:
                pass

    # 2. Mahsulotlar (UZ nom/tavsif + RU/EN tarjimalari)
    products = [
        # ── Burgerlar (cat 1) ─────────────────────────────────────────────────
        (1,  1, "Classic Burger",
         "Mol go'shti kotleti, bodring, pomidor, ketchup, mayonez.",
         "Классический бургер", "Котлета из говядины, огурец, помидор, кетчуп, майонез.",
         "Classic Burger", "Beef patty, pickles, tomato, ketchup, mayonnaise.",
         25000, "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500"),

        (2,  1, "Cheeseburger",
         "Cheddar pishloq, mol go'shti, salat bargi, maxsus sous.",
         "Чизбургер", "Сыр чеддер, говядина, лист салата, фирменный соус.",
         "Cheeseburger", "Cheddar cheese, beef, lettuce, special sauce.",
         28000, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500"),

        (3,  1, "Double Burger",
         "Ikkita kotlet, ikki qavat pishloq, maxsus sous.",
         "Двойной бургер", "Две котлеты, два слоя сыра, фирменный соус.",
         "Double Burger", "Two patties, double cheese, special sauce.",
         45000, "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?w=500"),

        (4,  1, "BBQ Burger",
         "BBQ sousi, qovurilgan piyoz, mol go'shti, dudlangan pishloq.",
         "BBQ Бургер", "Соус BBQ, жареный лук, говядина, копчёный сыр.",
         "BBQ Burger", "BBQ sauce, fried onions, beef, smoked cheese.",
         38000, "https://images.unsplash.com/photo-1553979459-d2229ba7433b?w=500"),

        (5,  1, "Chicken Burger",
         "Qovurilgan tovuq go'shti, coleslaw, ranch sousi.",
         "Чикен бургер", "Жареная куриная грудка, коулслоу, соус ранч.",
         "Chicken Burger", "Fried chicken breast, coleslaw, ranch sauce.",
         32000, "https://images.unsplash.com/photo-1626645738196-c2a7c87a8f58?w=500"),

        # ── Lavashlar (cat 2) ──────────────────────────────────────────────────
        (6,  2, "Mol go'shtli Lavash",
         "Mol go'shti, chips, bodring, pomidor, mayonez, ketchup.",
         "Лаваш с говядиной", "Говядина, чипсы, огурец, помидор, майонез, кетчуп.",
         "Beef Wrap", "Beef, chips, cucumber, tomato, mayo, ketchup.",
         30000, "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=500"),

        (7,  2, "Tovuqli Lavash",
         "Tovuq go'shti, chips, yangi sabzavotlar, garmdori sousi.",
         "Лаваш с курицей", "Курица, чипсы, свежие овощи, чесночный соус.",
         "Chicken Wrap", "Chicken, chips, fresh veggies, garlic sauce.",
         28000, "https://images.unsplash.com/photo-1600891964092-4316c288032e?w=500"),

        (8,  2, "Mini Lavash",
         "Kichikroq porsiya, ammo to'yimli va mazali.",
         "Мини лаваш", "Порция поменьше, но сытная и вкусная.",
         "Mini Wrap", "Smaller portion but filling and delicious.",
         22000, "https://images.unsplash.com/photo-1600891964599-f61ba0e24092?w=500"),

        (9,  2, "XL Lavash",
         "Katta porsiya mol go'shti lavash, ikki marta to'yimli.",
         "XL Лаваш", "Большая порция лаваша с говядиной, двойная сытность.",
         "XL Wrap", "Extra large beef wrap, twice as filling.",
         40000, "https://images.unsplash.com/photo-1585238341710-4d3ff484184d?w=500"),

        # ── Pitsalar (cat 3) ───────────────────────────────────────────────────
        (10, 3, "Pepperoni",
         "Klassik pepperoni, motsarella, tomat sousi.",
         "Пепперони", "Классическая пепперони, моцарелла, томатный соус.",
         "Pepperoni", "Classic pepperoni, mozzarella, tomato sauce.",
         65000, "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=500"),

        (11, 3, "Margarita",
         "Pomidor, rayhon, motsarella pishloqi.",
         "Маргарита", "Помидор, базилик, сыр моцарелла.",
         "Margherita", "Tomato, basil, mozzarella cheese.",
         55000, "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=500"),

        (12, 3, "BBQ Chicken Pizza",
         "Tovuq, BBQ sous, qizil piyoz, koriander.",
         "Пицца BBQ с курицей", "Курица, соус BBQ, красный лук, кинза.",
         "BBQ Chicken Pizza", "Chicken, BBQ sauce, red onion, cilantro.",
         70000, "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=500"),

        (13, 3, "Hawai Pizza",
         "Jambon, ananas, pishloq, tomat sousi.",
         "Гавайская пицца", "Ветчина, ананас, сыр, томатный соус.",
         "Hawaiian Pizza", "Ham, pineapple, cheese, tomato sauce.",
         68000, "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=500"),

        (14, 3, "4 Pishloqli",
         "Motsarella, cheddar, parmezan, gorgonzola.",
         "Четыре сыра", "Моцарелла, чеддер, пармезан, горгонзола.",
         "Four Cheese", "Mozzarella, cheddar, parmesan, gorgonzola.",
         72000, "https://images.unsplash.com/photo-1571407970349-bc81e7e96d47?w=500"),

        # ── Ichimliklar (cat 4) ────────────────────────────────────────────────
        (15, 4, "Coca Cola 0.5L",
         "Muzdek Coca-Cola.",
         "Кока-Кола 0.5Л", "Охлаждённая Кока-Кола.",
         "Coca Cola 0.5L", "Ice cold Coca-Cola.",
         8000, "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=500"),

        (16, 4, "Fanta 0.5L",
         "Apelsin ta'mli gazli ichimlik.",
         "Фанта 0.5Л", "Газированный напиток со вкусом апельсина.",
         "Fanta 0.5L", "Orange flavored carbonated drink.",
         8000, "https://images.unsplash.com/photo-1624517452488-04869289c4ca?w=500"),

        (17, 4, "Sprite 0.5L",
         "Limon-laym ta'mli muzdek ichimlik.",
         "Спрайт 0.5Л", "Охлаждённый напиток со вкусом лимона и лайма.",
         "Sprite 0.5L", "Lemon-lime flavored cold drink.",
         8000, "https://images.unsplash.com/photo-1625772452859-1c03d5bf1137?w=500"),

        (18, 4, "Apelsin Sharbat",
         "Yangi siqilgan apelsin sharbati.",
         "Апельсиновый сок", "Свежевыжатый апельсиновый сок.",
         "Fresh Orange Juice", "Freshly squeezed orange juice.",
         12000, "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=500"),

        (19, 4, "Milkshake",
         "Muzqaymoqli sut kokteyli — shokolad, vanil yoki qulupnay.",
         "Молочный коктейль", "Молочный коктейль с мороженым — шоколад, ваниль или клубника.",
         "Milkshake", "Ice cream milkshake — chocolate, vanilla or strawberry.",
         18000, "https://images.unsplash.com/photo-1579954115545-a95591f28bfc?w=500"),

        (20, 4, "Suv 0.5L",
         "Gazsiz toza ichimlik suvi.",
         "Вода 0.5Л", "Негазированная чистая питьевая вода.",
         "Water 0.5L", "Still clean drinking water.",
         3000, "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=500"),

        # ── Hot-doglar (cat 5) ─────────────────────────────────────────────────
        (21, 5, "Classic Hot-dog",
         "Sosiska, ketchup, xantal, non ichida.",
         "Классический хот-дог", "Сосиска, кетчуп, горчица, в булочке.",
         "Classic Hot Dog", "Sausage, ketchup, mustard, in a bun.",
         15000, "https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=500"),

        (22, 5, "Cheese Hot-dog",
         "Sosiska, eritilgan pishloq, xantal, mayonez.",
         "Сырный хот-дог", "Сосиска, плавленый сыр, горчица, майонез.",
         "Cheese Hot Dog", "Sausage, melted cheese, mustard, mayo.",
         18000, "https://images.unsplash.com/photo-1619740455993-9e612b1af08a?w=500"),

        (23, 5, "XXL Hot-dog",
         "Katta sosiska, ko'p sous, piyoz, bodring.",
         "XXL Хот-дог", "Большая сосиска, много соуса, лук, огурец.",
         "XXL Hot Dog", "Large sausage, lots of sauce, onion, pickle.",
         22000, "https://images.unsplash.com/photo-1591348278863-a8fb3887e2aa?w=500"),

        # ── Gazaklar (cat 6) ───────────────────────────────────────────────────
        (24, 6, "Kartoshka Fri",
         "Qovurilgan kartoshka, ketchup yoki sous bilan.",
         "Картошка фри", "Жареный картофель с кетчупом или соусом.",
         "French Fries", "Fried potatoes with ketchup or sauce.",
         12000, "https://images.unsplash.com/photo-1630384060421-cb20d0e0649d?w=500"),

        (25, 6, "Nuggets (6 dona)",
         "Tovuq nuggets, dippping sous bilan.",
         "Наггетсы (6 шт.)", "Куриные наггетсы с соусом для обмакивания.",
         "Nuggets (6 pcs)", "Chicken nuggets with dipping sauce.",
         18000, "https://images.unsplash.com/photo-1562802378-063ec186a863?w=500"),

        (26, 6, "Mozzarella Sticks",
         "Qovurilgan motsarella tayoqchalari, pomidor sousi bilan.",
         "Палочки моцарелла", "Жареные палочки моцареллы с томатным соусом.",
         "Mozzarella Sticks", "Fried mozzarella sticks with tomato sauce.",
         20000, "https://images.unsplash.com/photo-1548340748-6d2b7d7da280?w=500"),

        (27, 6, "Ketchup sousi",
         "Qo'shimcha ketchup sousi (100ml).",
         "Соус кетчуп", "Дополнительный кетчуп (100мл).",
         "Ketchup Sauce", "Extra ketchup sauce (100ml).",
         3000, "https://images.unsplash.com/photo-1461009683693-342af2f2d6ce?w=500"),

        # ── Donerlar (cat 7) ───────────────────────────────────────────────────
        (28, 7, "Toviuqli Doner",
         "Grillda pishirilgan tovuq go'shti, sabzavot, yogurt sousi.",
         "Донер с курицей", "Курица на гриле, овощи, йогуртовый соус.",
         "Chicken Doner", "Grilled chicken, vegetables, yogurt sauce.",
         32000, "https://images.unsplash.com/photo-1530469912745-a215c6b256ea?w=500"),

        (29, 7, "Mol go'shtli Doner",
         "Mol go'shti, lavash, pomidor, bodring, garmdori sousi.",
         "Донер с говядиной", "Говядина, лаваш, помидор, огурец, чесночный соус.",
         "Beef Doner", "Beef, flatbread, tomato, cucumber, garlic sauce.",
         35000, "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=500"),

        (30, 7, "Mix Doner",
         "Tovuq + mol go'shti aralash, barcha sous va sabzavotlar.",
         "Микс донер", "Курица + говядина, все соусы и овощи.",
         "Mix Doner", "Chicken + beef mix, all sauces and vegetables.",
         40000, "https://images.unsplash.com/photo-1529006557810-274b9b2fc783?w=500"),

        # ── KFC / Tovuqlar (cat 8) ─────────────────────────────────────────────
        (31, 8, "Qovurilgan Tovuq",
         "KFC uslubida qovurilgan tovuq bo'lagi (2 dona).",
         "Жареная курица", "Жареная курица в стиле KFC (2 шт.).",
         "Fried Chicken", "KFC-style fried chicken pieces (2 pcs).",
         28000, "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=500"),

        (32, 8, "Chicken Wings",
         "Achchiq-chuchuk sousi bilan tovuq qanotlari (6 dona).",
         "Куриные крылышки", "Куриные крылышки в кисло-сладком соусе (6 шт.).",
         "Chicken Wings", "Sweet and sour chicken wings (6 pcs).",
         30000, "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?w=500"),

        (33, 8, "Chicken Strips",
         "Krustonli tovuq po'stloqli tasmalar, ranch sousi bilan.",
         "Куриные стрипсы", "Куриные стрипсы в хрустящей панировке с соусом ранч.",
         "Chicken Strips", "Crispy breaded chicken strips with ranch sauce.",
         25000, "https://images.unsplash.com/photo-1619881590738-a111d176d906?w=500"),

        (34, 8, "Spicy Chicken",
         "Achchiq ziravorlarda marinlangan qovurilgan tovuq.",
         "Острая курица", "Жареная курица в остром маринаде.",
         "Spicy Chicken", "Fried chicken marinated in spicy seasoning.",
         32000, "https://images.unsplash.com/photo-1606755456206-b25206cde27e?w=500"),

        # ── Kombo to'plamlar (cat 9) ───────────────────────────────────────────
        (35, 9, "Burger Kombo",
         "Classic Burger + Kartoshka Fri + Coca Cola 0.5L.",
         "Бургер комбо", "Классический бургер + Картошка фри + Кока-Кола 0.5Л.",
         "Burger Combo", "Classic Burger + French Fries + Coca Cola 0.5L.",
         45000, "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?w=500"),

        (36, 9, "Oilaviy Kombo",
         "2ta Burger + 2ta Kartoshka + 2ta Ichimlik.",
         "Семейное комбо", "2 бургера + 2 картошки фри + 2 напитка.",
         "Family Combo", "2 Burgers + 2 Fries + 2 Drinks.",
         85000, "https://images.unsplash.com/photo-1550547660-d9450f859349?w=500"),

        (37, 9, "Pizza Kombo",
         "Margarita Pitsa + 2ta Ichimlik.",
         "Пицца комбо", "Пицца Маргарита + 2 напитка.",
         "Pizza Combo", "Margherita Pizza + 2 Drinks.",
         65000, "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=500"),

        (38, 9, "KFC Kombo",
         "2ta Qovurilgan Tovuq + Kartoshka Fri + Sprite.",
         "KFC комбо", "2 шт. жареной курицы + Картошка фри + Спрайт.",
         "KFC Combo", "2 pcs Fried Chicken + French Fries + Sprite.",
         55000, "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?w=500"),

        # ── Shirinliklar (cat 10) ──────────────────────────────────────────────
        (39, 10, "Shokoladli Tort",
         "Yumshoq shokoladli keks, krem bilan.",
         "Шоколадный торт", "Мягкий шоколадный кекс с кремом.",
         "Chocolate Cake", "Soft chocolate cake with cream.",
         18000, "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=500"),

        (40, 10, "Cheesecake",
         "Klassik limonli cheesecake, meva sousi bilan.",
         "Чизкейк", "Классический лимонный чизкейк с ягодным соусом.",
         "Cheesecake", "Classic lemon cheesecake with berry sauce.",
         22000, "https://images.unsplash.com/photo-1533134242443-d4fd215305ad?w=500"),

        (41, 10, "Muzqaymoq",
         "Vanil, shokolad yoki qulupnay — 2 sharli.",
         "Мороженое", "Ванильное, шоколадное или клубничное — 2 шарика.",
         "Ice Cream", "Vanilla, chocolate or strawberry — 2 scoops.",
         10000, "https://images.unsplash.com/photo-1501443762994-82bd5dace89a?w=500"),

        (42, 10, "Donut",
         "Glazurli va sprinkalali donut.",
         "Пончик", "Пончик с глазурью и посыпкой.",
         "Donut", "Glazed donut with sprinkles.",
         12000, "https://images.unsplash.com/photo-1551024601-bec78aea704b?w=500"),
    ]

    async with pool.acquire() as conn:
        for pid, cat_id, name, desc, name_ru, desc_ru, name_en, desc_en, price, img in products:
            exists = await conn.fetchval("SELECT id FROM products WHERE id = $1", pid)
            if not exists:
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
                    await conn.execute(
                        """
                        INSERT INTO products (id, category_id, name, description, price, image_url, is_active)
                        VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                        """,
                        pid, cat_id, name, desc, price, img
                    )
            # Mavjud mahsulotlarga tarjima yangilash
            try:
                await conn.execute(
                    """UPDATE products
                       SET name_ru = $1, name_en = $2,
                           description_ru = $3, description_en = $4
                       WHERE id = $5 AND (name_ru IS NULL OR name_en IS NULL)""",
                    name_ru, name_en, desc_ru, desc_en, pid
                )
            except Exception:
                pass
