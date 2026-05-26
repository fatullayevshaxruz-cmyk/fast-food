import asyncio
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from database.connection import init_db_pool, close_db_pool
from database.crud import init_database
from database.seed import seed_data
from database.db_manager import init_dynamic_menu_db
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Handlerlarni import qilish
from handlers.start import register_start_handlers
from handlers.menu import register_menu_handlers
from handlers.cart import register_cart_handlers
from handlers.order import register_order_handlers
from handlers.admin import register_admin_handlers
from handlers.profile import register_profile_handlers
from handlers.dynamic_menu import register_dynamic_menu_handlers
from handlers.payment import register_payment_handlers  # 💳 To'lov tizimi

# ── Self-ping: Render uxlab qolmasligi uchun ─────────────────────────
RENDER_URL = os.getenv("RENDER_URL", "https://fast-food-1-p4bx.onrender.com")
PING_INTERVAL = 10 * 60  # 10 daqiqa (Render 15 daqiqada uxlaydi)

async def keep_alive():
    """
    Har 10 daqiqada o'z-o'zini ping qiladi.
    Render free tier 15 daqiqa so'rov bo'lmasa uxlab qoladi —
    bu funksiya shu holatni oldini oladi.
    """
    await asyncio.sleep(30)  # Botning to'liq ishga tushishini kutish
    ping_url = f"{RENDER_URL}/health"
    fail_count = 0

    while True:
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20)
            ) as session:
                async with session.get(ping_url) as resp:
                    if resp.status == 200:
                        logging.info(f"✅ Keep-alive ping OK: {ping_url}")
                        fail_count = 0
                    else:
                        logging.warning(f"⚠️ Keep-alive ping: status {resp.status}")
                        fail_count += 1
        except asyncio.CancelledError:
            break
        except Exception as e:
            fail_count += 1
            logging.warning(f"⚠️ Keep-alive ping xatosi ({fail_count}): {e}")

        await asyncio.sleep(PING_INTERVAL)


async def on_startup(dp):
    await init_db_pool()
    await init_database()
    await seed_data()
    await init_dynamic_menu_db()
    logging.info("Database initialized, connected, and seeded.")


async def on_shutdown(dp):
    await close_db_pool()
    logging.info("Database connection closed.")
    await bot.close()


if __name__ == '__main__':
    from aiogram import executor
    from aiohttp import web

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Handlerlarni ro'yxatdan o'tkazish
    register_start_handlers(dp)
    register_menu_handlers(dp)
    register_cart_handlers(dp)
    register_order_handlers(dp)
    register_admin_handlers(dp)
    register_profile_handlers(dp)
    register_dynamic_menu_handlers(dp)
    register_payment_handlers(dp)    # 💳 To'lov tizimi (oxirida ro'yxatdan o'tkaziladi)

    # ── Health check web server ──────────────────────────────────────
    async def health_check(request):
        return web.Response(text="OK — Fast Food Bot is running! 🍔")

    async def start_web_server():
        app = web.Application()
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.getenv("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logging.info(f"Web server started on port {port}")

    # ── Tasklar ishga tushirish ──────────────────────────────────────
    loop.create_task(start_web_server())
    loop.create_task(keep_alive())   # 🔁 Self-ping har 10 daqiqada

    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        loop=loop
    )
