import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") # Can be a list of IDs separated by comma
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID", "-1003885234768")
BRANCH_1_CHANNEL_ID = os.getenv("BRANCH_1_CHANNEL_ID", "-1003885234768")  # 1-filial: Abu Ali ibn Sino ko'chasi
BRANCH_2_CHANNEL_ID = os.getenv("BRANCH_2_CHANNEL_ID", "-1003631903801")  # 2-filial: 5-mikrorayon
DELIVERY_CHANNEL_ID = os.getenv("DELIVERY_CHANNEL_ID", "-1003943860489")
DB_USER = os.getenv("DB_USER", "postgres")

DB_PASS = os.getenv("DB_PASS", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fastfood_bot")

POSTGRES_URI = (
    os.getenv("DATABASE_URL")
    or os.getenv("DB_URL")
    or f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")

PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN") # Click or Payme token

# Test provayder tokeni — Render'da PAYMENT_PROVIDER_TOKEN o'rnatilmagan bo'lsa ishlatiladi.
# Haqiqiy to'lov uchun Render → Environment da PAYMENT_PROVIDER_TOKEN ni haqiqiy token bilan qo'ying.
_DEFAULT_TEST_PAYMENT_TOKEN = "1650291590:TEST:1780943696815_x3KZ2Ie4RN3hPegD"
if not (PAYMENT_PROVIDER_TOKEN and PAYMENT_PROVIDER_TOKEN.strip()):
    PAYMENT_PROVIDER_TOKEN = _DEFAULT_TEST_PAYMENT_TOKEN

# ── Yangi sozlamalar ─────────────────────────────────────────────────

# Ish vaqti (soat)
WORKING_HOURS_START = int(os.getenv("WORKING_HOURS_START", "9"))   # 09:00
WORKING_HOURS_END   = int(os.getenv("WORKING_HOURS_END", "23"))    # 23:00

# Yetkazish narxi (so'mda)
DELIVERY_FEE = int(os.getenv("DELIVERY_FEE", "10000"))             # 10,000 so'm

# Minimal buyurtma summasi (yetkazish uchun)
MIN_ORDER_AMOUNT = int(os.getenv("MIN_ORDER_AMOUNT", "30000"))     # 30,000 so'm

# Online to'lov (karta) — standart holatda YOQILGAN
# .env / Render da ONLINE_PAYMENT_ENABLED=0 qilib o'chirish mumkin
ONLINE_PAYMENT_ENABLED = os.getenv("ONLINE_PAYMENT_ENABLED", "1") == "1"

# ── Restoran joylashuvi (Buxoro sh., 1-filial: Abu Ali ibn Sino ko'chasi) ──
RESTAURANT_LAT = float(os.getenv("RESTAURANT_LAT", "39.783420").replace(",", "."))
RESTAURANT_LON = float(os.getenv("RESTAURANT_LON", "64.422526").replace(",", "."))

# ── Masofaga qarab yetkazish narxi ───────────────────────────────────
# Birinchi FREE_KM km → BASE_FEE; har qo'shimcha km → EXTRA_PER_KM
DELIVERY_BASE_FEE      = int(os.getenv("DELIVERY_BASE_FEE", "10000"))    # 10,000 so'm
DELIVERY_EXTRA_PER_KM  = int(os.getenv("DELIVERY_EXTRA_PER_KM", "2000")) # 2,000 so'm/km
DELIVERY_FREE_KM       = float(os.getenv("DELIVERY_FREE_KM", "3.0"))     # 3 km gacha bepul

# ── Kuryer telefoni (yetkazilmoqda xabarida ko'rsatiladi) ────────────
COURIER_PHONE = os.getenv("COURIER_PHONE", "")   # misol: "+998901234567"
