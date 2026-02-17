import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from database.connection import init_db_pool, close_db_pool
from database.crud import init_database
from database.seed import seed_data
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage() # We can switch to RedisStorage later
dp = Dispatcher(bot, storage=storage)

# Handlerlarni import qilish
from handlers.start import register_start_handlers
from handlers.menu import register_menu_handlers
from handlers.cart import register_cart_handlers
from handlers.order import register_order_handlers
from handlers.admin import register_admin_handlers
from handlers.profile import register_profile_handlers


async def on_startup(dp):
    await init_db_pool()
    await init_database()
    await seed_data()
    logging.info("Database initialized, connected, and seeded.")


async def on_shutdown(dp):
    await close_db_pool()
    logging.info("Database connection closed.")
    await bot.close()

if __name__ == '__main__':
    from aiogram import executor
    
    # Fix for 'There is no current event loop'
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Register handlers
    register_start_handlers(dp)
    register_menu_handlers(dp)
    register_cart_handlers(dp)
    register_order_handlers(dp)
    register_admin_handlers(dp)
    register_profile_handlers(dp)
    
    
    # Render requires a web server to bind to a port for Web Services
    # We will start a dummy web server
    import os
    from aiohttp import web
    
    async def health_check(request):
        return web.Response(text="OK")
        
    async def start_web_server():
        app = web.Application()
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
        await site.start()
        logging.info(f"Web server started on port {os.getenv('PORT', 8080)}")

    loop.create_task(start_web_server())

    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True, loop=loop)



