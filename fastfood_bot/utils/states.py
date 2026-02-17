from aiogram.dispatcher.filters.state import State, StatesGroup

class OrderStates(StatesGroup):
    waiting_for_location = State()
    waiting_for_phone = State()
    waiting_for_payment = State()
    confirm_order = State()

class AdminStates(StatesGroup):
    broadcast_message = State()
    add_product = State()
