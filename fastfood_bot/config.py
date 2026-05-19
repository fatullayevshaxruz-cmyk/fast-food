import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") # Can be a list of IDs separated by comma
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID")
DB_USER = os.getenv("DB_USER", "postgres")

DB_PASS = os.getenv("DB_PASS", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "fastfood_bot")

POSTGRES_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")

PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN") # Click or Payme token

# ── Yangi sozlamalar ─────────────────────────────────────────────────

# Ish vaqti (soat)
WORKING_HOURS_START = int(os.getenv("WORKING_HOURS_START", "9"))   # 09:00
WORKING_HOURS_END   = int(os.getenv("WORKING_HOURS_END", "23"))    # 23:00

# Yetkazish narxi (so'mda)
DELIVERY_FEE = int(os.getenv("DELIVERY_FEE", "10000"))             # 10,000 so'm

# Minimal buyurtma summasi (yetkazish uchun)
MIN_ORDER_AMOUNT = int(os.getenv("MIN_ORDER_AMOUNT", "30000"))     # 30,000 so'm
