from aiogram.dispatcher.filters.state import State, StatesGroup

class OrderStates(StatesGroup):
    waiting_for_delivery_type = State()
    waiting_for_table_number = State()
    waiting_for_location = State()
    waiting_for_phone = State()
    waiting_for_payment = State()
    confirm_order = State()

class AdminStates(StatesGroup):
    broadcast_message = State()
    add_product = State()

# ── Dinamik menyu admin state lari ──────────────────────────────────
class DynamicMenuAdminStates(StatesGroup):
    # Taom qo'shish
    waiting_item_name        = State()
    waiting_item_price       = State()
    waiting_item_description = State()
    # Narx o'zgartirish (menyu boshqaruvi orqali)
    waiting_new_price        = State()
    # O'chirish (inline orqali, state shart emas)
    waiting_item_id_for_delete = State()

# ── Admin menyu ichidan narx o'zgartirish ────────────────────────────
class AdminProductStates(StatesGroup):
    waiting_new_price_inline = State()  # product_id saqlangan holda

