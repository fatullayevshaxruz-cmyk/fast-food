from aiogram import types, Dispatcher
from database.crud import create_user
from keyboards.main_menu import get_main_menu

async def cmd_start(message: types.Message):
    user = message.from_user
    await create_user(user.id, user.username, user.full_name)
    
    await message.answer(
        f"Assalomu alaykum, {user.full_name}! \n"
        "Xush kelibsiz! Bizning botimiz orqali mazali taomlarga buyurtma berishingiz mumkin.",
        reply_markup=get_main_menu()
    )

def register_start_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=['start'])
