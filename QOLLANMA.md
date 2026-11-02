# 🍔 Fast Food Telegram Boti — Foydalanish bo'yicha to'liq qo'llanma

Ushbu qo'llanma **Fast Food Bot** tizimining barcha funksiyalari, undan foydalanish tartibi va boshqaruv paneli (admin) imkoniyatlarini batafsil tushuntirib beradi.

---

## 📌 Mundarija
1. [🚀 Botni ishga tushirish](#1-botni-ishga-tushirish)
2. [📱 Foydalanuvchi funksiyalari (Mijozlar uchun)](#2-foydalanuvchi-funksiyalari-mijozlar-uchun)
3. [🛒 Buyurtma berish jarayoni](#3-buyurtma-berish-jarayoni)
4. [⭐ Fikr-mulohaza va baholash tizimi](#4-fikr-mulohaza-va-baholash-tizimi)
5. [👑 Admin panel imkoniyatlari (Boshqaruvchilar uchun)](#5-admin-panel-imkoniyatlari-boshqaruvchilar-uchun)
6. [🛠 Tizim komandalari (Commands)](#6-tizim-komandalari-commands)

---

## 1. 🚀 Botni ishga tushirish

Mijoz botga birinchi marta kirganda yoki `/start` buyrug'ini yuborganda quyidagi jarayon amalga oshadi:
1. **Tilni tanlash:** Bot foydalanuvchidan o'ziga qulay tilni tanlashni so'raydi:
   - 🇺🇿 O'zbekcha
   - 🇷🇺 Русский
   - 🇬🇧 English
2. **Ro'yxatdan o'tish:** Tizim foydalanuvchini avtomatik ravishda ma'lumotlar bazasiga kiritadi.
3. **Menyu tanlash:** Til tanlangandan so'ng, bot chiroyli kutib olish xabarini va menyuni ochish uchun 2 xil variantni taklif qiladi:
   - **🌐 Menu ilova** (Telegram WebApp / Mini App) — Zamonaviy va vizual chiroyli interaktiv menyu.
   - **📱 Menu** — An'anaviy matnli va inline tugmali Telegram menyusi.

---

## 2. 📱 Foydalanuvchi funksiyalari (Mijozlar uchun)

Foydalanuvchi asosiy menyu orqali quyidagi bo'limlardan foydalanishi mumkin:

* **🍽 Menyu (yoki 🌐 Tezkor buyurtma):**
  - Taomlar va ichimliklar kategoriyalarga bo'lingan holda ko'rsatiladi.
  - Mahsulotning rasmi, nomi, ta'rifi (tavsifi) va narxi ko'rsatiladi.
  - Har bir mahsulot ostida uning miqdorini belgilash (`-` va `+`) hamda **🛒 Savatchaga qo'shish** tugmalari mavjud.
  - Mahsulotni sevimli ro'yxatiga qo'shish uchun **❤️** (yurakcha) tugmasi mavjud.

* **🛒 Savatcha:**
  - Savatchaga qo'shilgan mahsulotlar ro'yxati, ularning miqdori va umumiy hisobi ko'rsatiladi.
  - Keraksiz mahsulotni ro'yxatdan o'chirish yoki savatni butunlay tozalash imkoniyati bor.
  - Yetkazib berish va muassasada tanovul qilish (Shu yerda) narxlari taqqoslanadi.
  - Agar buyurtma minimal summadan kam bo'lsa, tizim ogohlantiradi.

* **🔍 Qidiruv:**
  - Kalit so'z yoki taom nomi yozilganda, tizim mos keladigan mahsulotlarni tezkor qidirib topadi va tugmalar ko'rinishida taqdim etadi.

* **❤️ Tanlanganlar (Favorites):**
  - Foydalanuvchi o'ziga yoqqan va yurakcha belgisini bosgan barcha mahsulotlarni ushbu bo'limda tezda topishi mumkin.

* **📦 Buyurtmalarim:**
  - Mijozning oldingi buyurtmalari ro'yxati va ularning holati (kutilmoqda, tayyorlanmoqda, yo'lda, yakunlandi yoki bekor qilindi) ko'rsatiladi.
  - **🔄 Buyurtmani takrorlash** tugmasi orqali o'tgan buyurtmadagi barcha mahsulotlarni bir zumda savatchaga qayta yuklash mumkin.

* **👤 Profil:**
  - Mijozning ismi, telefon raqami va manzili ko'rsatiladi.
  - Xohlagan vaqtda ma'lumotlarni tahrirlash (ismni, telefon raqamini yoki manzilni o'zgartirish) imkoniyati mavjud.

* **☎️ Aloqa:**
  - Muassasa bilan bog'lanish ma'lumotlari, ish vaqti va lokatsiyasi ko'rsatiladi.

---

## 3. 🛒 Buyurtma berish jarayoni

Buyurtmani rasmiylashtirish (Checkout) bosqichma-bosqich amalga oshiriladi:

1. **Buyurtma turini tanlash:**
   - 🍽 **Shu yerda (Eat in):** Stol raqamini kiritish so'raladi va to'lovga o'tiladi.
   - 🛵 **Yetkazib berish (Delivery):** Manzil so'raladi.
2. **Manzilni yuborish (Yetkazib berish uchun):**
   - Foydalanuvchi matn shaklida manzil yozishi mumkin.
   - Telegram orqali joriy GPS joylashuvini yuborishi mumkin.
   - **📍 Xaritadan tanlash** (WebApp xaritasi) orqali xaritani ochib, aniq nuqtani belgilashi mumkin.
   * *Eslatma: Tizim faqat O'zbekiston hududidagi koordinatalarni qabul qiladi va Nominatim API yordamida koordinatalarni matnli manzilga o'giradi (Reverse geocoding).*
3. **Telefon raqami:**
   - Profilida raqam bo'lmasa, **📱 Raqamni yuborish** tugmasi yoki matn yordamida kiritiladi.
4. **Izoh kiritish:**
   - Buyurtma uchun qo'shimcha izoh yozish (masalan: *"Piyoz solmang"*) yoki o'tkazib yuborish mumkin.
5. **Promo kod (Chegirma):**
   - Agar promo kod mavjud bo'lsa, kiritiladi. Tizim promo kodning faolligini, muddati o'tmaganligini va oldin ishlatilmaganligini tekshirib, buyurtma summasiga chegirma hisoblaydi.
6. **To'lov usuli:**
   - 💵 **Naqd pul** (Yetkazib berilganda to'lash).
   - 💳 **Online to'lov** (Click yoki Payme orqali Telegram Payments tizimi).
7. **Yakunlash:**
   - Tizim buyurtmani rasmiylashtiradi va chek ko'rinishida foydalanuvchiga taqdim etadi.
   - Adminlarga (yoki maxsus guruh/kanalga) yangi buyurtma haqida to'liq ma'lumot (xarita havolasi bilan) yuboriladi.

---

## 4. ⭐ Fikr-mulohaza va baholash tizimi

Mijozlarning fikrini o'rganish va xizmat sifatini oshirish uchun botda avtomatlashtirilgan baholash tizimi ishlaydi:
1. Admin buyurtmani **"Yakunlandi" (Completed)** deb belgilaganidan 3 soniya o'tib, mijozga baholash so'rovi yuboriladi.
2. Mijoz 1 dan 5 gacha yulduzcha tanlaydi:
   - **4–5 yulduz (A'lo):** Bot mijozga minnatdorchilik bildiradi va jarayon yakunlanadi.
   - **1–3 yulduz (Past baho):** Bot past bahoning sababini so'raydi. Foydalanuvchi o'z e'tirozini yozib yuborishi yoki o'tkazib yuborishi mumkin.
3. Mijoz yozgan e'tiroz va past baho haqida **adminlarga (yoki admin kanaliga) zudlik bilan ogohlantirish xabari** boradi.

---

## 5. 👑 Admin panel imkoniyatlari (Boshqaruvchilar uchun)

Admin huquqiga ega foydalanuvchilar (ularning ID raqamlari bot sozlamalarida ko'rsatiladi) `/admin` komandasi orqali boshqaruv paneliga kirishlari mumkin:

* **📊 Statistika:**
  - Ro'yxatdan o'tgan foydalanuvchilar va jami buyurtmalar soni.
  - Bugungi kunlik buyurtmalar soni va jami tushum (daromad).
  - Eng ko'p sotilgan Top-5 mahsulotlar ro'yxati.

* **📢 Xabar tarqatish (Broadcast):**
  - Barcha bot a'zolariga reklama yoki e'lon xabarlarini yuborish.
  - Matnli yoki rasmli (rasm tagida matn bilan) xabarlarni tarqatish imkoniyati. Tizim xabar yuborishda bloklanishning oldini olish uchun kechikish (sleep) bilan ishlaydi.

* **📦 Buyurtmalarni boshqarish:**
  - So'nggi buyurtmalar ro'yxati va ularni filtrlash (Kutilayotgan, Tayyorlanmoqda, Yetkazilmoqda).
  - Har bir buyurtma holatini o'zgartirish tugmalari:
    - **🍳 Tayyorlashni boshlash**
    - **🛵 Yo'lga chiqish** (Mijozga kuryer telefon raqami bilan bildirishnoma boradi).
    - **✅ Yakunlash** (Mijozga baholash tizimi yuboriladi).
    - **❌ Bekor qilish**.
  * *Eslatma: Holat o'zgarganda mijozga chiroyli progress-bar ko'rinishida xabar boradi.*

* **➕ Mahsulot qo'shish:**
  - Bosqichma-bosqich yangi mahsulot qo'shish (Kategoriya tanlash -> Nomi -> Narxi -> Tavsifi -> Nom va tavsiflarning Rus/Ingliz tillaridagi tarjimasi -> Rasm yuborish).

* **⚙️ Mahsulotlarni tahrirlash (Inline menyu ichida):**
  - **🖼 Rasm almashish:** Mahsulot rasmiga yangi rasm yuborish yoki URL kiritish.
  - **🏷 Chegirma qo'shish:** Mahsulot uchun chegirmali narx belgilash (eski narx va yangi narx ko'rinishida chiqadi). Chegirmani bekor qilish.
  - **👁 Ko'rsatish / Yashirish:** Mahsulotni menyuda faol yoki nofaol qilish (yashirish).
  - **🌐 Tarjima qo'shish:** Mahsulot nomi va tavsifini boshqa tillar uchun tahrirlash.

* **🎟 Promo kodlar boshqaruvi:**
  - Tizimdagi promo kodlar ro'yxatini ko'rish va o'chirish.
  - Yangi promo kod yaratish (Kod nomi -> Chegirma foizi % -> Maksimal ishlatilish soni).

* **📥 Hisobot (CSV):**
  - Tizimdagi barcha buyurtmalarni Excel mos keladigan `.csv` formatida eksport qilib olish. Hisobotda buyurtma IDsi, mijoz ma'lumotlari, summa, manzil, buyurtma turi va sanasi batafsil keltiriladi.

---

## 6. 🛠 Tizim komandalari (Commands)

Botdagi mavjud rasmiy komandalar ro'yxati:

* `/start` — Botni birinchi marta ishga tushirish, qayta yuklash va tilni o'zgartirish.
* `/webapp` — Mini App interaktiv menyusini inline tugma orqali ochish.
* `/menu_refresh` — Asosiy menyu klaviaturasini yangilash (agar telefonlarda tugmalar ko'rinmay qolsa).
* `/help` — Yordam ma'lumotlari va qo'llab-quvvatlash xizmati.
* `/cancel` — Istalgan bosqichda faol jarayonni bekor qilib, asosiy menyuga qaytish.
* `/admin` — Boshqaruvchilar (adminlar) uchun boshqaruv panelini ochish.
