# 📖 Fast Food Telegram Boti — Ishlatish bo'yicha to'liq qo'llanma
*(Boshidan oxirigacha bo'lgan barcha jarayonlar bo'yicha batafsil yo'riqnoma)*

> **Eslatma:** Ushbu qo'llanma botning ichki dasturiy kodlari va funksiyalariga daxl qilmagan holda, faqat tizimni to'g'ri ishga tushirish, mijoz sifatida buyurtma berish hamda admin sifatida boshqarish jarayonlarini bosqichma-bosqich o'rgatadi.

---

## 📌 Mundarija
1. [⚙️ 1-Qism: Botni serverda / kompyuterda ishga tushirish](#️-1-qism-botni-serverda--kompyuterda-ishga-tushirish)
2. [📱 2-Qism: Mijoz (Foydalanuvchi) jarayoni — Boshidan oxirigacha](#-2-qism-mijoz-foydalanuvchi-jarayoni--boshidan-oxirigacha)
   - 1-qadam: Botga kirish va ro'yxatdan o'tish (`/start`)
   - 2-qadam: Tilni tanlash
   - 3-qadam: Menyu tanlash (Web App yoki Telegram menyusi)
   - 4-qadam: Taomlarni tanlash va savatchaga qo'shish
   - 5-qadam: Savatchani ko'rish va boshqarish
   - 6-qadam: Buyurtmani rasmiylashtirish (Checkout)
   - 7-qadam: Buyurtma holatini jonli kuzatish (Live Tracking)
   - 8-qadam: Taomni qabul qilish va xizmatni baholash (Feedback)
   - 9-qadam: Profil, Sevimlilar va Buyurtmalarni takrorlash
3. [👑 3-Qism: Admin (Boshqaruvchi) jarayoni — Boshidan oxirigacha](#-3-qism-admin-boshqaruvchi-jarayoni--boshidan-oxirigacha)
   - 1-qadam: Admin panelga kirish (`/admin`)
   - 2-qadam: Yangi buyurtmalarni qabul qilish va boshqarish
   - 3-qadam: Mijozlarning shikoyat va baholarini nazorat qilish
   - 4-qadam: Yangi mahsulot qo'shish va menyuni tahrirlash
   - 5-qadam: Chegirmalar va Promo-kodlar yaratish
   - 6-qadam: Reklama va xabar tarqatish (Broadcast)
   - 7-qadam: Kunlik tushum statistikasi va Excel (CSV) hisobot olish
4. [🛠 4-Qism: Tez-tez uchraydigan savollar va muammolarni hal qilish](#-4-qism-tez-tez-uchraydigan-savollar-va-muammolarni-hal-qilish)

---

## ⚙️ 1-Qism: Botni serverda / kompyuterda ishga tushirish

Botni ishlatishdan oldin u serverda yoki shaxsiy kompyuteringizda ishga tushirilgan bo'lishi kerak.

### 1. Talablar:
- **Python:** 3.10 yoki undan yuqori versiya.
- **Telegram Bot Token:** [@BotFather](https://t.me/BotFather) dan olingan token.

### 2. Sozlamalar (`.env` fayli):
`fastfood_bot/.env` faylida quyidagi asosiy parametrlar ko'rsatiladi:
```env
BOT_TOKEN=123456789:AAExampleToken...
ADMIN_ID=123456789,987654321
ADMIN_CHANNEL_ID=-1001234567890
WORKING_HOURS_START=9
WORKING_HOURS_END=23
DELIVERY_BASE_FEE=10000
DELIVERY_EXTRA_PER_KM=2000
DELIVERY_FREE_KM=3.0
MIN_ORDER_AMOUNT=30000
ONLINE_PAYMENT_ENABLED=1
RESTAURANT_LAT=41.2995
RESTAURANT_LON=69.2401
COURIER_PHONE=+998901234567
```

### 3. Ishga tushirish komandalari:
Terminal yoki buyruqlar satrida quyidagilarni bajaring:

```bash
# Loyiha papkasiga o'tish
cd fastfood_bot

# Virtual muhitni faollashtirish (agar mavjud bo'lsa)
source venv/bin/activate   # Linux/macOS
# yoki
venv\Scripts\activate      # Windows

# Kerakli kutubxonalarni tekshirish / o'rnatish
pip install -r requirements.txt

# Botni ishga tushirish
python bot.py
```

> **Eslatma:** Bot ishga tushgach, avtomatik ravishda ma'lumotlar bazasi va dastlabki taomlar menyusi yuklanadi hamda web-server faollashadi.

---

## 📱 2-Qism: Mijoz (Foydalanuvchi) jarayoni — Boshidan oxirigacha

Mijoz botdan foydalanishi uchun quyidagi bosqichlardan o'tadi:

```
[1. /start] ➜ [2. Til tanlash] ➜ [3. Menyu: WebApp / Telegram] ➜ [4. Taom tanlash] ➜
[5. Savat] ➜ [6. Buyurtma (Yetkazish/Shu yerda) + To'lov] ➜ [7. Jonli kuzatish] ➜ [8. Baholash]
```

---

### 1-qadam: Botga kirish va ro'yxatdan o'tish (`/start`)
1. Foydalanuvchi Telegram qidiruvidan bot nomini topadi yoki bot havolasiga bosadi.
2. Pastdagi **"Boshlash" (Start)** tugmasini bosadi yoki chatga `/start` deb yozadi.
3. Tizim foydalanuvchini avtomatik ravishda ma'lumotlar bazasida ro'yxatga oladi.

---

### 2-qadam: Tilni tanlash
Bot ekranda 3 xil til tanlash tugmasini chiqaradi:
- 🇺🇿 **O'zbekcha**
- 🇷🇺 **Русский**
- 🇬🇧 **English**

Foydalanuvchi o'ziga qulay tilni bir marta tanlaydi. Keyinchalik istalgan vaqtda tilni qayta o'zgartirish uchun yana `/start` yuborish kifoya.

---

### 3-qadam: Menyu formatini tanlash
Til tanlangach, bot xush kelibsiz xabarini yuboradi va menyuni ochishning 2 xil usulini taklif qiladi:
1. **🌐 Menu ilova (Telegram WebApp):**
   - Zamonaviy interaktiv Mini-ilova ochiladi.
   - Rasmlar, toifalar, animatsiyalar bilan qulay mobil dastur kabi ishlaydi.
2. **📱 Menu (Telegram menyusi):**
   - Telegram ichidagi an'anaviy tugmalar yordamida harakatlanish imkonini beradi.

---

### 4-qadam: Taomlarni tanlash va savatchaga qo'shish
1. **Kategoriyani tanlash:** Burgerlar, Lavashlar, Ichimliklar, Shirinliklar va h.k.
2. **Taom kartochkasi:**
   - Taomning yuqori sifatli rasmi, to'liq nomi, tavsifi va narxi ko'rsatiladi.
   - Agar chegirma bo'lsa, eski narx ustiga chizilgan holda yangi chegirmali narx ko'rsatiladi.
3. **Miqdorni belgilash:**
   - Taom ostidagi `➖` va `➕` tugmalari orqali nechta kerakligi tanlanadi (masalan, 2 ta).
4. **Savatchaga solish:**
   - **"🛒 Savatga qo'shish"** tugmasi bosiladi.
5. **Sevimli ro'yxatiga qo'shish:**
   - **❤️** tugmasini bosib, yoqtirgan taomlarini "Sevimlilar" ro'yxatiga saqlab qo'yish mumkin.
6. **Tezkor qidiruv:**
   - Agar mijoz ma'lum bir taomni qidirayotgan bo'lsa, asosiy menyudagi **"🔍 Qidiruv"** tugmasini bosib, taom nomini yozishi mumkin (masalan: `cheeseburger`). Bot mos keluvchi taomlarni bir zumda topib beradi.

---

### 5-qadam: Savatchani ko'rish va boshqarish
Barcha kerakli taomlar tanlangach, **"🛒 Savatcha"** tugmasi bosiladi:
- Savatchada barcha tanlangan taomlar ro'yxati, ularning soni, alohida narxlari va umumiy hisob ko'rinadi.
- Har bir mahsulot yonidagi `❌` tugmasini bosib, uni savatdan chiqarib tashlash mumkin.
- **"🗑 Savatni tozalash"** tugmasi orqali barcha mahsulotlarni birdan o'chirish mumkin.
- Pastdagi **"🛍 Buyurtma berish"** tugmasi bosiladi.

> **Eslatma:** Agar restoran belgilagan minimal buyurtma summasi (masalan, 30 000 so'm) to'lmagan bo'lsa, bot mijozdan yana taom qo'shishni so'raydi. Shuningdek, ish vaqtidan tashqarida (masalan, tungi 23:00 dan tonggi 09:00 gacha) buyurtma berilsa, bot ish vaqti haqida muloyim ogohlantirish beradi.

---

### 6-qadam: Buyurtmani rasmiylashtirish (Checkout jarayoni)

Buyurtma tugmasi bosilgach, bot qadamma-qadam quyidagi ma'lumotlarni so'raydi:

#### 1. Buyurtma turini tanlash:
- **🍽 Shu yerda (Restoranda):**
  - Bot: *"Stol raqamingizni kiriting:"* deb so'raydi. Mijoz o'tirgan stol raqamini (masalan: `12`) kiritadi.
- **🛵 Yetkazib berish (Delivery):**
  - Manzil so'raladi. Mijoz quyidagi 3 usuldan birida manzilni kiritishi mumkin:
    1. **Matn ko'rinishida:** Ko'cha va uy raqamini yozib yuborish (masalan: *"Chilonzor 9-mavze, 14-uy, 25-xonadon"*).
    2. **📍 Lokatsiya (GPS):** Telegram orqali jonli yoki hozirgi joylashuvni yuborish.
    3. **🌐 Xaritadan tanlash:** Interaktiv xarita (Mini App) ochiladi, xaritada markerni kerakli joyga qo'yib bitta bosish bilan manzil tasdiqlanadi.
    *(Tizim avtomatik ravishda restorandan mijozgacha bo'lgan masofani hisoblaydi va yetkazib berish xizmati narxini umumiy chekka qo'shadi).*

#### 2. Telefon raqamini tasdiqlash:
- Agar mijoz profilida telefon saqlangan bo'lsa, u avtomatik ishlatiladi.
- Agar birinchi marta bo'lsa, **"📱 Telefon raqamni yuborish"** tugmasi orqali yuboriladi yoki qo'lda kiritiladi.

#### 3. Qo'shimcha izoh (ixtiyoriy):
- Mijoz kuryer yoki oshpaz uchun eslatma qoldirishi mumkin (masalan: *"Domofon kodi: 45K, iltimos burgerga sous ko'proq bo'lsin"*).
- Izoh kerak bo'lmasa, **"➡️ O'tkazib yuborish"** tugmasi bosiladi.

#### 4. Promo-kod kiritish (ixtiyoriy):
- Agar mijozda chegirma promo-kodi bo'lsa (masalan: `NAVROZ20`), uni yozadi va summa avtomatik arzonlashadi. Promo-kod bo'lmasa, o'tkazib yuboriladi.

#### 5. To'lov usulini tanlash:
- **💵 Naqd pul:** Buyurtma yetkazib berilganda yoki stolda naqd to'lanadi.
- **💳 Online to'lov (Click / Payme):** Telegram orqali rasmiy to'lov cheki yuboriladi, mijoz ilova ichidan kartasi orqali to'lovni amalga oshiradi.

#### 6. Buyurtma tasdiqlandi:
- Mijozga rasmiy hisob-chek yuboriladi: Buyurtma raqami, taomlar ro'yxati, yetkazish narxi, umumiy summa va yetkazish manzili.
- Yangi buyurtma zudlik bilan restoran adminlariga yuboriladi.

---

### 7-qadam: Buyurtma holatini jonli kuzatish (Live Order Tracking)
Buyurtma tasdiqlangandan so'ng, mijoz hech qayoqqa telefon qilishi shart emas. Bot bosqichma-bosqich yangilanib turuvchi xabar yuboradi:

1. ⏳ **Qabul qilindi (Pending):** Buyurtma restoranga tushdi va tekshirilmoqda.  
   `[▶️⏳ ➜ 🍳 ➜ 🛵 ➜ ✅]`
2. 🍳 **Tayyorlanmoqda (Preparing):** Oshpaz taomni pishirishni boshladi.  
   `[✅ ➜ ▶️🍳 ➜ 🛵 ➜ ✅]`
3. 🛵 **Yetkazilmoqda (Delivering):** Taom tayyor bo'ldi, kuryer yo'lga chiqdi. *(Mijozga kuryerning telefon raqami ko'rsatiladi)*.  
   `[✅ ➜ ✅ ➜ ▶️🛵 ➜ ✅]`
4. ✅ **Yetkazib berildi (Completed):** Buyurtma mijozga topshirildi.  
   `[✅ ➜ ✅ ➜ ✅ ➜ ▶️✅]`

---

### 8-qadam: Taomni qabul qilish va xizmatni baholash (Feedback)
Buyurtma yetkazib berilgach (holati `Completed` bo'lgach), oradan 3 soniya o'tib bot mijozdan taom va xizmat sifatini baholashni so'raydi:
- Ekranda 5 ta yulduzcha chiqadi: `⭐ 1` | `⭐⭐ 2` | `⭐⭐⭐ 3` | `⭐⭐⭐⭐ 4` | `⭐⭐⭐⭐⭐ 5`
- **4 yoki 5 yulduz berilsa:** Bot mijozga samimiy minnatdorchilik bildiradi.
- **1, 2 yoki 3 yulduz berilsa:** Bot nima yoqmaganini so'raydi. Mijoz o'z e'tirozini yozadi. Bu shikoyat zudlik bilan restoran ma'muriyati (Adminlar kanali)ga yetkaziladi.

---

### 9-qadam: Qo'shimcha qulayliklar
- **📦 Buyurtmalarim:** O'tgan barcha buyurtmalar tarixi. Har birining chekini ko'rish va **"🔄 Qayta buyurtma berish"** tugmasi orqali o'sha taomlarni 1 soniyada yana savatga joylash mumkin.
- **❤️ Sevimlilar:** Yoqtirgan taomlar ro'yxatini tez topish.
- **👤 Profil:** Ism, telefon va manzilni istalgan payt yangilab qo'yish imkoniyati.
- **☎️ Aloqa:** Restoranning telefon raqami, ish vaqti va manzili.

---

## 👑 3-Qism: Admin (Boshqaruvchi) jarayoni — Boshqaruv qo'llanmasi

Restoran egasi, menejer yoki administrator botni boshqarishi uchun quyidagi tartibda ishlaydi:

---

### 1-qadam: Admin panelga kirish
1. Telegramda botga `/admin` buyrug'ini yuboring.  
   *(Faqat `.env` dagi `ADMIN_ID` ro'yxatida ko'rsatilgan akkauntlar kira oladi).*
2. Ekranda quyidagi tugmalarga ega boshqaruv paneli ochiladi:
   - 📊 **Statistika**
   - 📦 **Buyurtmalar**
   - ➕ **Mahsulot qo'shish**
   - 🎟 **Promo kodlar**
   - 📢 **Xabar tarqatish (Broadcast)**
   - 📥 **CSV Hisobot**

---

### 2-qadam: Yangi buyurtmalarni qabul qilish va holatini o'zgartirish
Yangi buyurtma tushganda admin yoki maxsus kanalga quyidagi ma'lumotlar bilan xabarnoma keladi:
- Buyurtma raqami, mijoz ismi va telefon raqami.
- Tanlangan taomlar, soni va umumiy summa.
- To'lov turi (Naqd yoki Online to'langan).
- Yetkazish manzili (Google Xarita ssilkasi bilan birga).

**Admin harakatlari:**
1. Buyurtmalar bo'limiga kiriladi (`📦 Buyurtmalar`).
2. Tegishli buyurtma tanlanadi.
3. Holat ketma-ket almashtiriladi:
   - Taom oshxonada pishirilayotganda ➡️ **"🍳 Tayyorlash"** tugmasi bosiladi *(mijozga xabar boradi)*.
   - Taom kuryerga topshirilganda ➡️ **"🛵 Yo'lga chiqish"** tugmasi bosiladi *(mijozga kuryer raqami boradi)*.
   - Kuryer taomni topshirib pulni olgach ➡️ **"✅ Yakunlash"** tugmasi bosiladi *(mijozga baholash tizimi boradi)*.
   - Biror sabab bilan buyurtma to'xtatilsa ➡️ **"❌ Bekor qilish"** tugmasi bosiladi.

---

### 3-qadam: Mijozlarning shikoyat va baholarini nazorat qilish
- Agar biror mijoz buyurtmaga 1, 2 yoki 3 yulduz qo'yib, shikoyat yozsa, bu xabar avtomatik tarzda `ADMIN_CHANNEL_ID` ga boradi.
- Admin ushbu mijoz bilan telefon orqali bog'lanib, vaziyatni tezda ijobiy tomonga hal qilishi mumkin.

---

### 4-qadam: Menyu boshqaruvi (Yangi taom qo'shish va tahrirlash)

#### Yangi taom qo'shish:
1. Admin panelda **"➕ Mahsulot qo'shish"** tugmasi bosiladi.
2. Bot ketma-ket so'raydi:
   - Kategoriya tanlang (Burger, Lavash, Ichimlik va h.k.).
   - Mahsulot nomini kiriting (masalan: *Duble Burger*).
   - Narxini kiriting (faqat raqam, masalan: `38000`).
   - Tavsifini kiriting (tarkibi va ta'rifi).
   - Rus va inglizcha tarjimalari (so'ralsa kiritiladi yoki o'tkazib yuboriladi).
   - Rasm yuboring (Telegram orqali taom rasmi jo'natiladi).
3. Yangi taom darhol barcha foydalanuvchilar menyusida paydo bo'ladi.

#### Mavjud taomni tahrirlash (Inline menyu):
Menyudagi mahsulot ostidagi maxsus tugmalar orqali admin quyidagilarni qila oladi:
- **🖼 Rasm almashish:** Eski rasm o'rniga yangi sifatli rasm yuklash.
- **🏷 Chegirma qo'shish:** Mahsulotga chegirmali narx kiritish (masalan, 40 000 so'mlik taomni 32 000 so'm qilib belgilash).
- **👁 Yashirish / Ko'rsatish:** Mahsulot vaqtincha tugab qolgan bo'lsa, uni menyudan o'chirib yubormasdan, bir tugma bilan vaqtincha yashirib qo'yish.

---

### 5-qadam: Chegirmalar va Promo-kodlar yaratish
1. **"🎟 Promo kodlar"** bo'limiga kiriladi.
2. **"➕ Yangi promo kod"** tugmasi bosiladi.
3. Sozlamalar kiritiladi:
   - Promo-kod nomi (masalan: `SUPER20`).
   - Chegirma foizi (masalan: `20`).
   - Ishlatishlar soni (masalan: dastlabki `50` ta mijoz uchun).
4. Promo-kod tayyor! Uni ijtimoiy tarmoqlarda yoki reklama xabarnomasida e'lon qilish mumkin.

---

### 6-qadam: Reklama va xabar tarqatish (Broadcast)
Barcha bot foydalanuvchilariga bir vaqtda aksiyalar yoki yangiliklar haqida e'lon yuborish:
1. **"📢 Xabar tarqatish"** tugmasi bosiladi.
2. Xabar matni yoki rasm tagiga izoh yozib yuboriladi.
3. Bot avtomatik ravishda barcha ro'yxatdan o'tgan foydalanuvchilarga xabarni tarqatadi.

---

### 7-qadam: Kunlik statistika va Excel (CSV) hisobotlar
- **📊 Statistika:**
  - Jami foydalanuvchilar soni.
  - Bugungi buyurtmalar soni va jami tushgan pul summasi.
  - Eng ko'p sotilayotgan **Top-5** taomlar ro'yxati.
- **📥 CSV Hisobot:**
  - Barcha buyurtmalar tarixi jamlangan Excelda ochiladigan `.csv` faylini bir zumda yuklab olish. Hisobotda har bir mijoz, summa, sana va manzillar to'liq aks etadi.

---

## 🛠 4-Qism: Tez-tez uchraydigan savollar va muammolarni hal qilish

| Savol / Muammo | Sababi va Yechimi |
| :--- | :--- |
| **Klaviaturadagi tugmalar ko'rinmay qoldi** | Mijoz `/menu_refresh` yoki `/start` buyrug'ini yuborishi kerak. Bu tugmalarni qayta chizib beradi. |
| **"Hozirda dam olish vaqti" degan xabar chiqmoqda** | `.env` dagi `WORKING_HOURS_START` va `WORKING_HOURS_END` soatlari tekshiriladi. Hozirgi soat ushbu oraliqda bo'lmasa, bot buyurtma olmaydi. |
| **Kuryerga yetkazish narxi qanday hisoblanadi?** | Masofa restoranning GPS koordinatalari (`RESTAURANT_LAT`, `RESTAURANT_LON`) bilan mijoz koordinatasi orasidagi to'g'ri masofa asosida avtomatik hisoblanadi (`DELIVERY_BASE_FEE` + har km uchun `DELIVERY_EXTRA_PER_KM`). |
| **Promo-kod ishlamayapti** | Promo-kodning muddati tugagan, limiti to'lgan yoki foydalanuvchi uni oldin ishlatgan bo'lishi mumkin. |
| **Admin panelga kirib bo'lmayapti** | Sizning Telegram ID raqamingiz `.env` faylidagi `ADMIN_ID` qatoriga yozilganligiga ishonch hosil qiling. |

---

*Hujjat muallifi: Fast Food Bot boshqaruv tizimi*
