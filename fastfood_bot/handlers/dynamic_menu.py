"""
handlers/dynamic_menu.py
------------------------
Dinamik menyu tizimining barcha handlerlari.

Foydalanuvchi: "🛠 Admin menu" tugmasini bosib real-time narxlarni ko'radi.
Admin:         "🛠 Menyu boshqaruvi" tugmasi orqali taom qo'shadi,
               narx o'zgartiradi va taomni o'chiradi — kod o'zgartirilmaydi.

MUHIM: Bu fayl mavjud handlerlarga HECH QANDAY ta'sir qilmaydi.
"""

import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext

from config import ADMIN_ID
from database.crud import get_user_language
from database.db_manager import (
    dm_add_item,
    dm_get_all_items,
    dm_get_item_by_id,
    dm_update_price,
    dm_delete_item,
    format_menu_text,
)
from keyboards.admin_keyboard import (
    get_dynamic_menu_admin_keyboard,
    get_items_inline_keyboard,
)
from utils.states import DynamicMenuAdminStates, AdminProductStates
from utils.i18n import get_text


# ─────────────────────────────────────────────
# Yordamchi
# ─────────────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    allowed = [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return str(user_id) in allowed


# ─────────────────────────────────────────────
# FOYDALANUVCHI: "🛠 Admin menyu" → Menyuni ko'rish
# ─────────────────────────────────────────────

async def user_show_dynamic_menu(message: types.Message):
    from database.crud import get_categories
    from keyboards.product_keyboard import get_admin_categories_markup
    lang = await get_user_language(message.from_user.id)
    categories = await get_categories()
    if not categories:
        await message.answer(get_text("menu_empty_admin", lang))
        return
    await message.answer(
        get_text("menu_panel_title", lang),
        reply_markup=get_admin_categories_markup(categories),
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# ADMIN: "🛠 Menyu boshqaruvi" → Panel
# ─────────────────────────────────────────────

async def admin_open_dynamic_panel(message: types.Message):
    if not _is_admin(message.from_user.id):
        lang = await get_user_language(message.from_user.id)
        await message.answer(get_text("no_permission", lang))
        return
    lang = await get_user_language(message.from_user.id)
    await message.answer(
        get_text("dm_panel_title", lang),
        reply_markup=get_dynamic_menu_admin_keyboard(lang),
        parse_mode="HTML"
    )


async def admin_back_from_dynamic_panel(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.finish()
    from keyboards.main_menu import get_admin_main_menu
    lang = await get_user_language(message.from_user.id)
    await message.answer(get_text("dm_back_to_admin", lang), reply_markup=get_admin_main_menu(lang))


# ─────────────────────────────────────────────
# ADMIN: "📝 Menyuni ko'rish"
# ─────────────────────────────────────────────

async def admin_view_dynamic_menu(message: types.Message):
    if not _is_admin(message.from_user.id):
        lang = await get_user_language(message.from_user.id)
        await message.answer(get_text("no_permission", lang))
        return
    lang = await get_user_language(message.from_user.id)
    from database.crud import get_categories
    from keyboards.product_keyboard import get_categories_markup
    categories = await get_categories()
    if not categories:
        await message.answer(get_text("menu_empty_admin", lang), reply_markup=get_dynamic_menu_admin_keyboard(lang))
        return
    await message.answer(
        get_text("menu_panel_title", lang),
        reply_markup=get_categories_markup(categories, lang=lang),
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# ADMIN: "➕ Taom qo'shish" (3 bosqich)
# ─────────────────────────────────────────────

async def admin_start_add_item(message: types.Message):
    if not _is_admin(message.from_user.id):
        lang = await get_user_language(message.from_user.id)
        await message.answer(get_text("no_permission", lang))
        return
    lang = await get_user_language(message.from_user.id)
    await DynamicMenuAdminStates.waiting_item_name.set()
    await message.answer(get_text("dm_add_title", lang), parse_mode="HTML")


async def admin_receive_item_name(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("dm_cancelled", lang), reply_markup=get_dynamic_menu_admin_keyboard(lang))
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer(get_text("dm_name_too_short", lang))
        return
    await state.update_data(item_name=name)
    await DynamicMenuAdminStates.waiting_item_price.set()
    await message.answer(get_text("dm_ask_price", lang, name=name), parse_mode="HTML")


async def admin_receive_item_price(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("dm_cancelled", lang), reply_markup=get_dynamic_menu_admin_keyboard(lang))
        return
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer(get_text("dm_price_invalid", lang))
        return
    await state.update_data(item_price=price)
    await DynamicMenuAdminStates.waiting_item_description.set()
    await message.answer(
        f"✅ {get_text('price_label', lang, price=price)}\n\n"
        + get_text("dm_ask_description", lang),
        parse_mode="HTML"
    )


async def admin_receive_item_description(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("dm_cancelled", lang), reply_markup=get_dynamic_menu_admin_keyboard(lang))
        return
    description = "" if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    item_id = await dm_add_item(
        name=data["item_name"],
        price=data["item_price"],
        description=description
    )
    await state.finish()
    price_label = get_text("price_label", lang, price=data["item_price"])
    await message.answer(
        get_text("dm_add_success", lang,
                 id=item_id, name=data["item_name"],
                 price_label=price_label,
                 desc=description or "—"),
        parse_mode="HTML",
        reply_markup=get_dynamic_menu_admin_keyboard(lang)
    )
    logging.info(f"Admin {message.from_user.id} yangi taom qo'shdi: #{item_id} {data['item_name']}")


# ─────────────────────────────────────────────
# ADMIN: "💰 Narx o'zgartirish"
# ─────────────────────────────────────────────

async def admin_start_change_price(message: types.Message):
    if not _is_admin(message.from_user.id):
        lang = await get_user_language(message.from_user.id)
        await message.answer(get_text("no_permission", lang))
        return
    lang = await get_user_language(message.from_user.id)
    items = await dm_get_all_items()
    if not items:
        await message.answer(get_text("dm_menu_empty", lang))
        return
    markup = get_items_inline_keyboard(items, action="price", lang=lang)
    await message.answer(get_text("dm_select_price_title", lang), reply_markup=markup, parse_mode="HTML")


async def admin_select_item_for_price(call: types.CallbackQuery, state: FSMContext):
    lang = await get_user_language(call.from_user.id)
    item_id = int(call.data.split("_")[2])
    item = await dm_get_item_by_id(item_id)
    if not item:
        await call.answer(get_text("dm_not_found", lang), show_alert=True)
        return
    await state.update_data(change_price_item_id=item_id)
    await DynamicMenuAdminStates.waiting_new_price.set()
    await call.message.edit_text(
        f"✅ {item['name']}\n"
        f"{get_text('price_label', lang, price=item['price'])}\n\n"
        f"{get_text('admin_price_ask', lang)}\n"
        f"<i>Bekor qilish: /bekor</i>",
        parse_mode="HTML"
    )
    await call.answer()


async def admin_receive_new_price(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("dm_cancelled", lang), reply_markup=get_dynamic_menu_admin_keyboard(lang))
        return
    try:
        new_price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer(get_text("dm_price_invalid", lang))
        return
    data = await state.get_data()
    item_id = data["change_price_item_id"]
    item = await dm_get_item_by_id(item_id)
    success = await dm_update_price(item_id, new_price)
    await state.finish()
    if success and item:
        await message.answer(
            get_text("dm_price_updated", lang, name=item['name']) + "\n"
            + get_text("admin_old_price", lang, old=item['price'], new=new_price),
            parse_mode="HTML",
            reply_markup=get_dynamic_menu_admin_keyboard(lang)
        )
        logging.info(f"Admin {message.from_user.id} #{item_id} narxini {new_price} ga o'zgartirdi")
    else:
        await message.answer("❌ Xatolik yuz berdi.", reply_markup=get_dynamic_menu_admin_keyboard(lang))


# ─────────────────────────────────────────────
# ADMIN: "🗑 Taomni o'chirish"
# ─────────────────────────────────────────────

async def admin_start_delete_item(message: types.Message):
    if not _is_admin(message.from_user.id):
        lang = await get_user_language(message.from_user.id)
        await message.answer(get_text("no_permission", lang))
        return
    lang = await get_user_language(message.from_user.id)
    items = await dm_get_all_items()
    if not items:
        await message.answer(get_text("dm_menu_empty", lang))
        return
    markup = get_items_inline_keyboard(items, action="delete", lang=lang)
    await message.answer(get_text("dm_select_delete_title", lang), reply_markup=markup, parse_mode="HTML")


async def admin_confirm_delete_item(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    item_id = int(call.data.split("_")[2])
    item = await dm_get_item_by_id(item_id)
    if not item:
        await call.answer(get_text("dm_delete_not_found", lang), show_alert=True)
        return
    success = await dm_delete_item(item_id)
    if success:
        await call.message.edit_text(
            get_text("dm_delete_success", lang, name=item['name']),
            parse_mode="HTML"
        )
        logging.info(f"Admin {call.from_user.id} #{item_id} taomni o'chirdi")
    else:
        await call.message.edit_text(get_text("dm_delete_not_found", lang))
    await call.answer()


# ─────────────────────────────────────────────
# Callback: Bekor qilish
# ─────────────────────────────────────────────

async def admin_cancel_callback(call: types.CallbackQuery, state: FSMContext):
    lang = await get_user_language(call.from_user.id)
    await state.finish()
    await call.message.edit_text(get_text("dm_cancelled", lang))
    await call.answer()


# ─────────────────────────────────────────────
# ADMIN MENYU: kategoriya → mahsulot
# ─────────────────────────────────────────────

async def admin_show_category_products(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        lang = await get_user_language(call.from_user.id)
        await call.answer(get_text("no_permission", lang), show_alert=True)
        return
    from database.connection import get_db_pool
    category_id = int(call.data.split("_")[2])
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch("SELECT * FROM products WHERE category_id = $1 ORDER BY id", int(category_id))
    lang = await get_user_language(call.from_user.id)
    if not products:
        await call.answer(get_text("category_empty", lang), show_alert=True)
        return
    await call.message.delete()
    await _send_admin_product_page(call, products[0], category_id, 0, len(products))
    await call.answer()


async def admin_paginate_products(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        lang = await get_user_language(call.from_user.id)
        await call.answer(get_text("no_permission", lang), show_alert=True)
        return
    from database.connection import get_db_pool
    parts = call.data.split("_")
    category_id = int(parts[2])
    index = int(parts[3])
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch("SELECT * FROM products WHERE category_id = $1 ORDER BY id", int(category_id))
    lang = await get_user_language(call.from_user.id)
    if not products or index < 0 or index >= len(products):
        await call.answer(get_text("no_more_products", lang))
        return
    await _send_admin_product_page(call, products[index], category_id, index, len(products), is_edit=True)
    await call.answer()


async def admin_back_to_categories(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        lang = await get_user_language(call.from_user.id)
        await call.answer(get_text("no_permission", lang), show_alert=True)
        return
    from database.crud import get_categories
    from keyboards.product_keyboard import get_admin_categories_markup
    lang = await get_user_language(call.from_user.id)
    try:
        await call.message.delete()
    except Exception:
        pass
    categories = await get_categories()
    await call.message.answer(
        get_text("menu_panel_title", lang),
        reply_markup=get_admin_categories_markup(categories),
        parse_mode="HTML"
    )
    await call.answer()


async def _send_admin_product_page(call, product, category_id, index, total, is_edit=False):
    from keyboards.product_keyboard import get_admin_product_markup
    old_price = None
    is_active = True
    try:
        old_price = product['old_price']
    except (KeyError, IndexError):
        pass
    try:
        is_active = product['is_active']
    except (KeyError, IndexError):
        pass

    has_discount = bool(old_price and old_price > product['price'])
    lang = await get_user_language(call.from_user.id)

    caption = f"<b>{product['name']}</b>\n\n"
    if product['description']:
        caption += f"{product['description']}\n\n"
    if has_discount:
        caption += get_text("price_discount_label", lang, old=old_price, new=product['price']) + "\n"
    else:
        caption += get_text("price_label", lang, price=product['price']) + "\n"
    if not is_active:
        caption += get_text("product_hidden_note", lang) + "\n"
    caption += get_text("product_counter", lang, cur=index + 1, total=total)

    markup = get_admin_product_markup(product['id'], category_id, index, total,
                                       is_active=is_active, has_discount=has_discount)
    if is_edit:
        try:
            if product['image_url']:
                media = types.InputMediaPhoto(media=product['image_url'], caption=caption, parse_mode="HTML")
                await call.message.edit_media(media, reply_markup=markup)
            else:
                await call.message.edit_text(caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            try:
                await call.message.delete()
            except Exception:
                pass
            await _safe_send_product(call.message, product, caption, markup)
    else:
        await _safe_send_product(call.message, product, caption, markup)


async def _safe_send_product(message, product, caption, markup):
    if product['image_url']:
        try:
            await message.answer_photo(photo=product['image_url'], caption=caption,
                                       reply_markup=markup, parse_mode="HTML")
        except Exception:
            await message.answer(caption, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=markup, parse_mode="HTML")


async def admin_inline_price_start(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        lang = await get_user_language(call.from_user.id)
        await call.answer(get_text("no_permission", lang), show_alert=True)
        return
    from database.crud import get_product
    lang = await get_user_language(call.from_user.id)
    product_id = int(call.data.split("_")[2])
    product = await get_product(product_id)
    if not product:
        await call.answer(get_text("product_not_found", lang), show_alert=True)
        return
    await state.update_data(admin_price_product_id=product_id)
    await AdminProductStates.waiting_new_price_inline.set()
    await call.message.answer(
        f"✏️ <b>{product['name']}</b>\n"
        f"{get_text('price_label', lang, price=product['price'])}\n\n"
        f"{get_text('admin_price_ask', lang)}",
        parse_mode="HTML"
    )
    await call.answer()


async def admin_inline_price_receive(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    try:
        new_price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer(get_text("dm_price_invalid", lang))
        return
    data = await state.get_data()
    product_id = data["admin_price_product_id"]
    from database.crud import get_product
    from database.connection import get_db_pool
    product = await get_product(product_id)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE products SET price = $1 WHERE id = $2", new_price, product_id)
    await state.finish()
    await message.answer(
        get_text("dm_price_updated", lang, name=product['name']) + "\n"
        + get_text("admin_old_price", lang, old=product['price'], new=new_price),
        parse_mode="HTML"
    )
    logging.info(f"Admin {message.from_user.id} #{product_id} mahsulot narxini {new_price} ga o'zgartirdi")


# ─────────────────────────────────────────────
# Handler ro'yxatdan o'tkazish
# ─────────────────────────────────────────────

def register_dynamic_menu_handlers(dp: Dispatcher):

    # Barcha 3 tildagi tugma matnlari
    _ADMIN_MENU_TEXTS = [
        "🛠 Admin menyu", "🛠 Меню админа", "🛠 Admin Menu",
        "🛠 Admin menu",
    ]
    _MENU_MGMT_TEXTS = [
        "🛠 Menyu boshqaruvi", "🛠 Управление меню", "🛠 Menu Management",
    ]
    _BACK_TEXTS = [
        "⬅️ Orqaga", "⬅️ Назад", "⬅️ Back",
    ]
    _VIEW_MENU_TEXTS = [
        "📝 Menyuni ko'rish", "📝 Просмотр меню", "📝 View Menu",
    ]
    _ADD_DISH_TEXTS = [
        "➕ Taom qo'shish", "➕ Добавить блюдо", "➕ Add Dish",
    ]
    _CHANGE_PRICE_TEXTS = [
        "💰 Narx o'zgartirish", "💰 Изменить цену", "💰 Change Price",
    ]
    _DELETE_DISH_TEXTS = [
        "🗑 Taomni o'chirish", "🗑 Удалить блюдо", "🗑 Delete Dish",
    ]

    dp.register_message_handler(
        user_show_dynamic_menu,
        lambda m: m.text in _ADMIN_MENU_TEXTS, state="*"
    )
    dp.register_message_handler(
        admin_open_dynamic_panel,
        lambda m: m.text in _MENU_MGMT_TEXTS, state="*"
    )
    dp.register_message_handler(
        admin_back_from_dynamic_panel,
        lambda m: m.text in _BACK_TEXTS, state="*"
    )
    dp.register_message_handler(
        admin_view_dynamic_menu,
        lambda m: m.text in _VIEW_MENU_TEXTS, state="*"
    )
    dp.register_message_handler(
        admin_start_add_item,
        lambda m: m.text in _ADD_DISH_TEXTS, state="*"
    )
    dp.register_message_handler(admin_receive_item_name, state=DynamicMenuAdminStates.waiting_item_name)
    dp.register_message_handler(admin_receive_item_price, state=DynamicMenuAdminStates.waiting_item_price)
    dp.register_message_handler(admin_receive_item_description, state=DynamicMenuAdminStates.waiting_item_description)
    dp.register_message_handler(
        admin_start_change_price,
        lambda m: m.text in _CHANGE_PRICE_TEXTS, state="*"
    )
    dp.register_callback_query_handler(
        admin_select_item_for_price,
        lambda c: c.data and c.data.startswith("dm_price_"), state="*"
    )
    dp.register_message_handler(admin_receive_new_price, state=DynamicMenuAdminStates.waiting_new_price)
    dp.register_message_handler(
        admin_start_delete_item,
        lambda m: m.text in _DELETE_DISH_TEXTS, state="*"
    )
    dp.register_callback_query_handler(
        admin_confirm_delete_item,
        lambda c: c.data and c.data.startswith("dm_delete_"), state="*"
    )
    dp.register_callback_query_handler(
        admin_cancel_callback,
        lambda c: c.data == "dm_cancel", state="*"
    )
    dp.register_callback_query_handler(
        admin_show_category_products,
        lambda c: c.data and c.data.startswith("admin_cat_"), state="*"
    )
    dp.register_callback_query_handler(
        admin_paginate_products,
        lambda c: c.data and c.data.startswith("admin_paginate_"), state="*"
    )
    dp.register_callback_query_handler(
        admin_back_to_categories,
        lambda c: c.data == "admin_back_to_cats", state="*"
    )
    dp.register_callback_query_handler(
        admin_inline_price_start,
        lambda c: c.data and c.data.startswith("admin_price_"), state="*"
    )
    dp.register_message_handler(
        admin_inline_price_receive,
        state=AdminProductStates.waiting_new_price_inline
    )
