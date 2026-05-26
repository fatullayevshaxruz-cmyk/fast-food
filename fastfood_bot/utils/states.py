from aiogram.dispatcher.filters.state import State, StatesGroup

class OrderStates(StatesGroup):
    waiting_for_delivery_type = State()
    waiting_for_table_number = State()
    waiting_for_location = State()
    waiting_for_phone = State()
    waiting_for_payment = State()
    waiting_for_note = State()
    waiting_for_promo = State()           # Promo kod
    waiting_for_payment_method = State()  # To'lov usuli (naqd / online)
    confirm_order = State()

class AdminStates(StatesGroup):
    broadcast_message = State()

class AddProductStates(StatesGroup):
    waiting_category    = State()
    waiting_name        = State()
    waiting_price       = State()
    waiting_description = State()
    waiting_image       = State()

class DynamicMenuAdminStates(StatesGroup):
    waiting_item_name        = State()
    waiting_item_price       = State()
    waiting_item_description = State()
    waiting_new_price        = State()
    waiting_item_id_for_delete = State()

class AdminProductStates(StatesGroup):
    waiting_new_price_inline  = State()
    waiting_new_image         = State()
    waiting_discount_price    = State()

class SearchStates(StatesGroup):
    waiting_query = State()

class ProfileStates(StatesGroup):
    editing_name    = State()
    editing_phone   = State()
    editing_address = State()

class PromoCodeStates(StatesGroup):
    waiting_code            = State()
    waiting_discount        = State()
    waiting_max_uses        = State()
