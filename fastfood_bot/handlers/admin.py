from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from config import ADMIN_ID
from keyboards.admin_keyboard import get_admin_keyboard
from utils.states import AdminStates
from database.connection import get_db_pool

async def cmd_admin(message: types.Message):
    # Check if user is admin
    if str(message.from_user.id) not in ADMIN_ID.split(','):
        return
    
    await message.answer("Admin panelga xush kelibsiz!", reply_markup=get_admin_keyboard())

async def stats_handler(message: types.Message):
    if str(message.from_user.id) not in ADMIN_ID.split(','):
        return
    
    pool = await get_db_pool()
    users_count = await pool.fetchval("SELECT COUNT(*) FROM users")
    orders_count = await pool.fetchval("SELECT COUNT(*) FROM orders")
    
    await message.answer(
        f"📊 **Statistika**\n\n"
        f"👤 Foydalanuvchilar: {users_count}\n"
        f"📦 Buyurtmalar: {orders_count}"
    )

async def start_broadcast(message: types.Message):
    if str(message.from_user.id) not in ADMIN_ID.split(','):
        return
        
    await AdminStates.broadcast_message.set()
    await message.answer("Xabar matnini yuboring (yoki rasmli xabar):")

async def send_broadcast(message: types.Message, state: FSMContext):
    # Simple broadcast to all users (warning: can be slow/blocking for large userbase)
    # Ideally should be a background task or batch job
    text = message.text or message.caption
    photo = message.photo[-1].file_id if message.photo else None
    
    pool = await get_db_pool()
    users = await pool.fetch("SELECT user_id FROM users")
    
    count = 0
    for i, user in enumerate(users):
        try:
            if photo:
                await message.bot.send_photo(user['user_id'], photo, caption=text)
            else:
                await message.bot.send_message(user['user_id'], text)
            count += 1
        except Exception:
            pass # Blocked or deactivated
            
        # Avoid flood limits (approx 20 messages per second safe limit)
        if (i + 1) % 20 == 0:
            await asyncio.sleep(1.0)
            
    await message.answer(f"Xabar {count} ta foydalanuvchiga yuborildi.")
    await state.finish()

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_admin, commands=['admin'])
    dp.register_message_handler(stats_handler, text="📊 Statistika")
    dp.register_message_handler(start_broadcast, text="📢 Xabar tarqatish")
    dp.register_message_handler(send_broadcast, state=AdminStates.broadcast_message, content_types=types.ContentTypes.ANY)
