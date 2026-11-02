# 🍔 Fast Food Telegram Boti va WebApp Tizimining Barcha Funksiyalari hamda Ishlash Prinspi

Ushbu hujjat **Fast Food Telegram Bot** va **Web Mini App** tizimidagi barcha funksiyalar, texnik arxitektura, koddagi handlerlar va ularning ishlash mexanizmlarini to'liq tavsiflaydi.

---

## 📌 Mundarija
1. [🏗 Tizim Arxitekturasi va Ishga Tushish Mexanizmi](#1-tizim-arxitekturasi-va-ishga-tushish-mexanizmi)
2. [📱 Foydalanuvchi Funksiyalari (Mijozlar uchun)](#2-foydalanuvchi-funksiyalari-mijozlar-uchun)
3. [🛒 Buyurtma Berish Jarayoni (Checkout Workflow)](#3-buyurtma-berish-jarayoni-checkout-workflow)
4. [⭐ Baholash va Buyurtma Holatini Kuzatish (Live Tracking & Feedback)](#4-baholash-va-buyurtma-holatini-kuzatish-live-tracking--feedback)
5. [👑 Admin Panel Funksiyalari (Boshqaruvchilar uchun)](#5-admin-panel-funksiyalari-boshqaruvchilar-uchun)
6. [🌐 REST API va WebApp (Mini App Integration)](#6-rest-api-va-webapp-mini-app-integration)
7. [🗄 Ma'lumotlar Bazasi va Modellari](#7-malumotlar-bazasi-va-modellari)
8. [🛠 Tizim Komandalari (Bot Commands)](#8-tizim-komandalari-bot-commands)

---

## 1. 🏗 Tizim Arxitekturasi va Ishga Tushish Mexanizmi

Bot va Web server **Python 3.10+** muhitida **Aiogram 2.x** va **aiohttp** frameworklari yordamida yozilgan.

### 🔹 Ishga tushish jarayoni (`bot.py`):
1. **Bazalarni retsializatsiya qilish:**
   - `init_db_pool()` va `init_database()`: PostgreSQL (`asyncpg`) yoki SQLite bazasiga ulanadi va jadval sxemalarini yaratadi.
   - `seed_data()`: Dastlabki kategoriya va mahsulotlarni kiritadi.
   - `init_dynamic_menu_db()`: Dinamik menyu bazasini ishga tushiradi.
2. **Bot komandalarini ro'yxatdan o'tkazish:**
   - BotFather ga kirmasdan `/start`, `/webapp`, `/menu_refresh`, `/help`, `/cancel` komandalarini avtomatik menyuda ko'rsatish so'raladi.
3. **Web Server & REST API:**
   - `aiohttp.web.Application` asosida port (masalan: 8080) ochiladi.
   - WebApp statik fayllari (`/webapp/app.html`, `/webapp/map.html`) tarqatiladi.
   - REST API handlerlari (`webapp_api.py`) ro'yxatdan o'tkaziladi.
4. **Render Keep-Alive Mexanizmi (`keep_alive()`):**
   - Render.com bepul serverlarida 15 daqiqa so'rov bo'lmasa, server uxlab qoladi.
   - `keep_alive()` funksiyasi har 10 daqiqada `/health` manziliga o'z-o'ziga ping yuborib, serverni doimy faol ushlab turadi.

---

## 2. 📱 Foydalanuvchi Funksiyalari (Mijozlar uchun)

Foydalanuvchiga taqdim etiladigan barcha imkoniyatlar 3 tilda (**O'zbek, Rus, Ingliz**) to'liq qo'llab-quvvatlanadi (`utils/i18n.py`).

### 1️⃣ Tilni Tanlash va Ro'yxatdan O'tish (`handlers/start.py`)
- `/start` yuborilganda foydalanuvchi ma'lumotlar bazasida yaratiladi (`create_user`).
- Til tanlash klaviaturalari ko'rsatiladi: `🇺🇿 O'zbek`, `🇷🇺 Русский`, `🇬🇧 English`.
- Til tanlangach, **🌐 Menu ilova** (Telegram WebApp) va **📱 Menu** (Oddiy Telegram menyusi) tanlash taklifi chiqadi.

### 2️⃣ Menyu va Mahsulotlarni Ko'rish (`handlers/menu.py`)
- **Kategoriyalar:** Taomlar kategoriyalar bo'yicha guruhlangan.
- **Mahsulot Sahifalari (Inline Pagination):**
  - Rasm, nom, tavsif va narx ko'rsatiladi.
  - Chegirma mavjud bo'lsa, eski va yangi narx taqqoslab ko'rsatiladi.
  - `-` va `+` tugmalari orqali soni o'zgartiriladi.
  - `🛒 Savatga qo'shish` tugmasi orqali mahsulot savatga qo'shiladi.
  - `❤️` (Sevimli) tugmasi orqali taom sevimli ro'yxatga qo'shiladi/o'chiriladi (`toggle_favorite`).

### 3️⃣ Qidiruv Tizimi (`handlers/menu.py`)
- **🔍 Izlash:** Kalit so'z yozilganda, bazadan `LIKE` operatori orqali mahsulotlar izlanadi (`search_products`).
- Natijalar inline tugmalar shaklida chiqariladi va bosilganda to'g'ridan-to'g'ri o'sha mahsulot kartochkasi ochiladi.

### 4️⃣ Savatcha Boshqaruvi (`handlers/cart.py`)
- **🛒 Savat:** Savatdagi mahsulotlar ro'yxati, soni, har birining va umumiy summasi ko'rsatiladi.
- **Birma-bir o'chirish:** Har bir mahsulot yonidagi ❌ tugmasi orqali savatdan olib tashlanadi.
- **Savatni tozalash:** Tasdiqlash modal oynasi (`Ha` / `Yo'q`) orqali savat to'liq tozalanadi.
- **Taqqoslama:** "Shu yerda" va "Yetkazib berish" narxlari ko'rsatiladi.
- **Minimal summa tekshiruvi:** Agar summa `MIN_ORDER_AMOUNT` dan kam bo'lsa, ogohlantirish beriladi.

### 5️⃣ Sevimlilar (`handlers/profile.py`)
- **❤️ Sevimlilar:** Foydalanuvchi yoqtirgan va yurakcha bosgan barcha taomlar bir joyda jamlanadi.

### 6️⃣ Buyurtmalarim va Takrorlash (`handlers/profile.py`)
- **📦 Buyurtmalarim:** Foydalanuvchining barcha o'tgan buyurtmalari va ularning joriy holati (`pending`, `preparing`, `delivering`, `completed`, `cancelled`).
- **Batafsil chek:** Buyurtma IDsi bosilganda uning ichki mahsulotlari va manzili ko'rinadi.
- **🔄 Buyurtmani takrorlash (`repeat_order_to_cart`):** Eski buyurtmadagi barcha mahsulotlarni 1 bosqichda qayta savatga yuklaydi.

### 7️⃣ Shaxsiy Profil (`handlers/profile.py`)
- **👤 Profil:** Mijozning ismi, telefon raqami va standart manzili ko'rsatiladi.
- **Tahrirlash:**
  - `✏️ Ismni o'zgartirish` (`update_user_name`)
  - `📞 Telefonni o'zgartirish` (`update_user_phone`)
  - `📍 Manzilni o'zgartirish` (`update_user_address`)

---

## 3. 🛒 Buyurtma Berish Jarayoni (Checkout Workflow)

Buyurtma berish `handlers/order.py` va `handlers/payment.py` fayllari orqali ketma-ket (FSM State) amalga oshiriladi:

```
[Savat] ──> [Buyurtma turi: Shu yerda / Delivery] ──> [Stol raqami YOKI Manzil]
                │
                ├──> [GPS / Matn / WebApp Xarita] ──> [Telefon kiritish / Saqlangan]
                │
                └──> [Izoh qoldirish / O'tkazib yuborish] ──> [Promo kod kiritish]
                                                                  │
                                                                  └──> [To'lov: Naqd / Online (Click/Payme)]
```

### 🔹 Ishlash tartibi:
1. **Ish vaqti tekshiruvi:** `WORKING_HOURS_START` (masalan, 09:00) va `WORKING_HOURS_END` (23:00) oralig'ida bo'lmasa, buyurtma qabul qilinmaydi.
2. **Buyurtma turi:**
   - **🍽 Shu yerda (Eat-in):** Stol raqami so'raladi va to'lovga o'tiladi.
   - **🛵 Yetkazib berish (Delivery):** Manzil so'raladi.
3. **Manzilni aniqlash:**
   - **Matnli manzil:** Foydalanuvchi yozgan ko'cha nomi.
   - **GPS Joylashuv:** Telegram lokatsiyasi.
   - **🌐 WebApp Xaritasi (`map.html`):** Interaktiv xarita orqali aniq koordinatani belgilash.
   - **Geografik chegaralash:** Faqat O'zbekiston koordinatalari qabul qilinadi (`_is_in_uzbekistan`).
   - **Reverse Geocoding (`_reverse_geocode`):** OpenStreetMap Nominatim API orqali koordinatalar matnli ko'cha va mahalla nomiga avtomatik aylantiriladi.
   - **Masofaviy Yetkazib Berish Narxi (`calculate_delivery_fee`):** Restoran koordinatasidan mijozgacha bo'lgan masofa (Haversine formulasi) hisoblanadi va narx 1000 so'mgacha yaxlitlanadi.
4. **Telefon va Izoh:** Telefon raqami bazada bo'lsa avtomatik ishlatiladi, aks holda tugma orqali so'raladi. Izoh (masalan: *"Piyoz solmang"*) kiritilishi mumkin.
5. **Promo Kod System (`process_promo`):**
   - Promo kod mavjudligi, amal qilish muddati, ishlatilish limiti va foydalanuvchi oldin ishlatgani tekshiriladi (`check_user_promo_used`).
   - Chegirma foizi summa hisobiga ayiriladi.
6. **To'lov Usullari (`handlers/payment.py`):**
   - **💵 Naqd pul:** Buyurtma to'g'ridan-to'g'ri yaratiladi va adminga xabar ketadi.
   - **💳 Online To'lov (Click / Payme):** Telegram Payments API orqali `send_invoice` yuboriladi. `pre_checkout_query` tekshirilib, `successful_payment` kelgach buyurtma bazaga saqlanadi.

---

## 4. ⭐ Baholash va Buyurtma Holatini Kuzatish (Live Tracking & Feedback)

### 🛵 Live Order Tracking (`handlers/order_tracking.py`)
Admin buyurtma holatini o'zgartirganda, mijozga avtomatik ravishda chiroyli progress-bar bilan xabar yuboriladi:
- ⏳ **Pending:** *Buyurtmangiz qabul qilindi* `[▶️⏳ ➜ 🍳 ➜ 🛵 ➜ ✅]`
- 🍳 **Preparing:** *Taomlar tayyorlanmoqda* `[✅ ➜ ▶️🍳 ➜ 🛵 ➜ ✅]`
- 🛵 **Delivering:** *Kuryer yo'lda* `[✅ ➜ ✅ ➜ ▶️🛵 ➜ ✅]` *(Kuryer telefon raqami ko'rsatiladi)*
- ✅ **Completed:** *Buyurtma yakunlandi* `[✅ ➜ ✅ ➜ ✅ ➜ ▶️✅]`
- ❌ **Cancelled:** *Bekor qilindi*

### ⭐ Avtomatlashtirilgan Baholash Tizimi (`handlers/feedback.py`)
1. Buyurtma **"Completed"** bo'lgandan **3 soniya o'tib** mijozga 1-5 yulduzli inline baholash tugmalari boradi (`send_feedback_request`).
2. Mijoz baholaydi:
   - **4–5 ⭐ (Yuqori baho):** Bot mijozga minnatdorchilik bildiradi.
   - **1–3 ⭐ (Past baho):** Bot past bahoning sababini so'raydi. Foydalanuvchi sababini yozib yuboradi yoki `/skip` bosadi.
3. Past baho va bildirilgan e'tiroz **zudlik bilan Adminlar kanaliga/guruhiga (`ADMIN_CHANNEL_ID`)** xabar shaklida yuboriladi (`_notify_admins_bad_rating`).

---

## 5. 👑 Admin Panel Funksiyalari (Boshqaruvchilar uchun)

`/admin` komandasi orqali kiriladi (faqat `ADMIN_ID` ruxsati bor foydalanuvchilar uchun).

### 1️⃣ Statistika (`stats_handler`)
- Jami foydalanuvchilar va buyurtmalar soni.
- Kutilayotgan buyurtmalar.
- Bugungi kunlik buyurtmalar va jami tushum summasi.
- Eng ko'p sotilgan **Top-5 mahsulotlar**.

### 2️⃣ Xabar Tarqatish / Broadcast (`send_broadcast`)
- Barcha bot foydalanuvchilariga matnli yoki rasmli reklamalarni tarqatish.
- Telegram cheklovlariga (Anti-flood) tushmaslik uchun har 20 ta xabarda 1 soniyalik kechikish yuboriladi.

### 3️⃣ Buyurtmalarni Boshqarish (`admin_orders`)
- Buyurtmalar ro'yxati va holat bo'yicha filtrlash (Kutilayotgan, Tayyorlanmoqda, Barchasi).
- Buyurtma kartasini ko mehanizmi (mijoz ismi, telefoni, manzili, taomlar va jami summa).
- Holatni o'zgartirish tugmalari: `🍳 Tayyorlash`, `🛵 Yo'lga chiqish`, `✅ Yakunlash`, `❌ Bekor qilish`.

### 4️⃣ Mahsulot Qo'shish (`admin_start_add_product`)
5 bosqichli FSM oqimi:
1. Kategoriya tanlash -> 2. Nomini kiritish -> 3. Narxini kiritish -> 4. Tavsif kiritish -> 5. Rus/Ingliz tillaridagi tarjimalari -> 6. Rasm yuborish/URL.

### 5️⃣ Inline Mahsulot Tahrirlash
- **🖼 Rasm almashish:** Yangi rasm yuborish (`update_product_image`).
- **🏷 Chegirma qo'shish/o'chirish:** Chegirmali narx belgilash (`set_product_discount`).
- **👁 Ko'rsatish/Yashirish:** Mahsulotni menyuda faol yoki nofaol qilish (`toggle_product_active`).
- **🌐 Tarjima qo'shish:** Mahsulot nomlari va tavsiflarini tahrirlash (`admin_trans_desc_en`).

### 6️⃣ Dinamik Menyu Boshqaruvi (`handlers/dynamic_menu.py`)
- Real-time rejimda kodga tegmasdan taom qo'shish, narxini o'zgartirish va taomni o'chirish panelini taqdim etadi.

### 7️⃣ Promo Kodlar Boshqaruvi (`admin_promo_list`)
- Mavjud promo kodlarni ko'rish va o'chirish (`delete_promo_code`).
- Yangi promo kod yaratish: Kod nomi -> Chegirma foizi (%) -> Maksimal ishlatish soni.

### 8️⃣ CSV Hisobot Eksporti (`admin_csv_export`)
- Barcha buyurtmalarni Excel mos keladigan `.csv` (UTF-8 BOM bilan) faylida yuklab olish.
- Hisobotda Buyurtma ID, Mijoz, Telefon, Summa, Turi, Manzil, Izoh, Holat va Sana keltiriladi.

---

## 6. 🌐 REST API va WebApp (Mini App Integration)

Bot aiohttp web server bilan integratsiya qilingan bo'lib, Telegram Mini App uchun quyidagi REST API nuqtalarini taqdim etadi (`webapp_api.py`):

| Endpoint | Method | Vazifasi |
| :--- | :---: | :--- |
| `/health` | `GET` | Server salomatligini tekshirish (Keep-alive) |
| `/api/menu` | `GET` | Barcha kategoriyalar va mahsulotlar JSON ko'rinishida |
| `/api/user` | `GET` | Mijoz profili va buyurtmalar tarixi |
| `/api/profile/update` | `POST` | Mijoz telefon raqamini tahrirlash |
| `/api/favorites` | `GET` | Mijozning sevimli taomlari ro'yxati |
| `/api/favorites/toggle`| `POST` | Sevimlilar ro'yxatiga qo'shish/o'chirish |
| `/api/search` | `GET` | WebApp ichida taomlarni tezkor qidirish |
| `/api/promo` | `GET` | Promo kod yaroqliligini va chegirma foizini tekshirish |
| `/api/order/create` | `POST` | WebApp Mini App ichidan buyurtma rasmiylashtirish |
| `/api/admin/dashboard`| `GET` | Admin panel uchun statistik ma'lumotlar |
| `/api/admin/orders` | `GET` | Admin uchun buyurtmalar ro'yxati |
| `/api/admin/order/status` | `POST` | Admin tomonidan buyurtma holatini o'zgartirish |
| `/api/admin/products` | `POST` | WebApp orqali mahsulot qo'shish/tahrirlash/o'chirish |
| `/api/admin/categories`| `POST` | WebApp orqali kategoriyalarni boshqarish |

---

## 7. 🗄 Ma'lumotlar Bazasi va Modellari

Baza sxemalari `database/crud.py` va `database/models.py` da aniqlangan:

1. **`users`**: `user_id` (PK), `username`, `full_name`, `phone_number`, `default_address`, `language`, `created_at`.
2. **`categories`**: `id` (PK), `name`, `name_ru`, `name_en`, `emoji`.
3. **`products`**: `id` (PK), `category_id`, `name`, `name_ru`, `name_en`, `description`, `description_ru`, `description_en`, `price`, `old_price`, `image_url`, `is_active`.
4. **`cart`**: `id` (PK), `user_id`, `product_id`, `quantity`.
5. **`orders`**: `id` (PK), `user_id`, `total_amount`, `status`, `delivery_address`, `payment_method`, `latitude`, `longitude`, `phone_number`, `note`, `delivery_type`, `rating`, `rating_comment`, `created_at`.
6. **`order_items`**: `id` (PK), `order_id`, `product_id`, `quantity`, `price_at_time`.
7. **`favorites`**: `id` (PK), `user_id`, `product_id`.
8. **`promo_codes`**: `code` (PK), `discount_percent`, `max_uses`, `used_count`, `is_active`.
9. **`user_promo_usage`**: `user_id`, `promo_code`, `used_at`.

---

## 8. 🛠 Tizim Komandalari (Bot Commands)

- `/start` — Botni qayta ishga tushirish va tilni tanlash.
- `/webapp` — Mini App interaktiv menyusini inline tugma orqali ochish.
- `/menu_refresh` — Asosiy menyu klaviaturasini qayta yuklash (tugmalar yo'qolganda).
- `/help` — Yordam va qo'llab-quvvatlash ma'lumotlari.
- `/cancel` — Har qanday faol jarayonni/FSM ni bekor qilish.
- `/admin` — Boshqaruv paneli (faqat adminlar uchun).

---
*Ushbu qo'llanma Fast Food Telegram Bot tizimining to'liq va rasmiy funksional hujjati hisoblanadi.*
