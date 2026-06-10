"""
handlers/dynamic_menu.py
------------------------
Dinamik menyu tizimining barcha handlerlari.

Foydalanuvchi: "📋 Dinamik Menyu" tugmasini bosib real-time narxlarni ko'radi.
Admin:         "🛠 Menyu boshqaruvi" tugmasi orqali taom qo'shadi,
               narx o'zgartiradi va taomni o'chiradi — kod o'zgartirilmaydi.

MUHIM: Bu fayl mavjud handlerlarga HECH QANDAY ta'sir qilmaydi.
"""

import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

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
    """Foydalanuvchi admin ekanligini tekshiradi."""
    allowed = [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return str(user_id) in allowed


# ─────────────────────────────────────────────
# FOYDALANUVCHI: Menyuni ko'rish
# ─────────────────────────────────────────────

async def user_show_dynamic_menu(message: types.Message):
    """
    '🛠 Admin menu' tugmasi bosilganda kategoriyalar admin_cat_ callbacklari bilan chiqadi.
    """
    from database.crud import get_categories
    from keyboards.product_keyboard import get_admin_categories_markup

    categories = await get_categories()
    if not categories:
        await message.answer("⚠️ Menyu bo'sh.")
        return

    await message.answer(
        "🍽 <b>Menyu</b>\nQuyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_admin_categories_markup(categories),
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# ADMIN: Menyu boshqaruvi bo'limine kirish
# ─────────────────────────────────────────────

async def admin_open_dynamic_panel(message: types.Message):
    """Admin '🛠 Menyu boshqaruvi' tugmasini bosganida panel ochiladi."""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ Sizda bu funksiyaga ruxsat yo'q.")
        return
    await message.answer(
        "🛠 <b>Dinamik Menyu Boshqaruvi</b>\n\n"
        "Quyidagi amallardan birini tanlang:",
        reply_markup=get_dynamic_menu_admin_keyboard(),
        parse_mode="HTML"
    )


async def admin_back_from_dynamic_panel(message: types.Message, state: FSMContext):
    """'⬅️ Orqaga' — asosiy menyu klaviaturasiga qaytish."""
    if not _is_admin(message.from_user.id):
        return
    await state.finish()
    from keyboards.main_menu import get_admin_main_menu
    from database.crud import get_user_language
    lang = await get_user_language(message.from_user.id)
    await message.answer("Admin paneliga qaytdingiz.", reply_markup=get_admin_main_menu(lang))


# ─────────────────────────────────────────────
# ADMIN: Admin panelidan menyuni ko'rish
# ─────────────────────────────────────────────

async def admin_view_dynamic_menu(message: types.Message):
    """Admin '📝 Menyuni ko'rish' — xuddi mijoz menuday kategoriyalar inline bilan."""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q.")
        return

    from database.crud import get_categories
    from keyboards.product_keyboard import get_categories_markup

    categories = await get_categories()
    if not categories:
        await message.answer("⚠️ Menyu bo'sh.", reply_markup=get_dynamic_menu_admin_keyboard())
        return

    await message.answer(
        "🍽 <b>Menyu</b>\nQuyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_categories_markup(categories),
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# ADMIN: Yangi taom qo'shish (3 bosqich)
# ─────────────────────────────────────────────

async def admin_start_add_item(message: types.Message):
    """Yangi taom qo'shish jarayonini boshlaydi."""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q.")
        return
    await DynamicMenuAdminStates.waiting_item_name.set()
    await message.answer(
        "🍽 <b>Yangi taom qo'shish</b>\n\n"
        "Taomning <b>nomini</b> yozing:\n"
        "<i>(Bekor qilish uchun /bekor yozing)</i>",
        parse_mode="HTML"
    )


async def admin_receive_item_name(message: types.Message, state: FSMContext):
    """1-qadam: Taom nomini qabul qilish."""
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_dynamic_menu_admin_keyboard())
        return

    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Taom nomi kamida 2 ta harf bo'lishi kerak. Qaytadan yozing:")
        return

    await state.update_data(item_name=name)
    await DynamicMenuAdminStates.waiting_item_price.set()
    await message.answer(
        f"✅ Nom: <b>{name}</b>\n\n"
        "Endi taomning <b>narxini</b> yozing (faqat son, so'mda):\n"
        "<i>Masalan: 25000</i>",
        parse_mode="HTML"
    )


async def admin_receive_item_price(message: types.Message, state: FSMContext):
    """2-qadam: Narxni qabul qilish."""
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_dynamic_menu_admin_keyboard())
        return

    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Narx musbat son bo'lishi kerak. Qaytadan yozing:")
        return

    await state.update_data(item_price=price)
    await DynamicMenuAdminStates.waiting_item_description.set()
    lang = await get_user_language(message.from_user.id)
    cur = get_text("currency", lang)
    await message.answer(
        f"✅ {get_text('price_label', lang, price=price)}\n\n"
        "Taomning <b>tavsifini</b> yozing (ixtiyoriy):\n"
        "<i>O'tkazib yuborish uchun — tire ( - ) yuboring</i>",
        parse_mode="HTML"
    )


async def admin_receive_item_description(message: types.Message, state: FSMContext):
    """3-qadam: Tavsifni qabul qilib, bazaga saqlash."""
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_dynamic_menu_admin_keyboard())
        return

    description = "" if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()

    item_id = await dm_add_item(
        name=data["item_name"],
        price=data["item_price"],
        description=description
    )

    await state.finish()
    lang = await get_user_language(message.from_user.id)
    await message.answer(
        f"🎉 <b>Taom muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🆔 ID: <b>{item_id}</b>\n"
        f"🍽 Nomi: <b>{data['item_name']}</b>\n"
        f"💰 {get_text('price_label', lang, price=data['item_price'])}\n"
        f"📝 Tavsif: {description or '—'}",
        parse_mode="HTML",
        reply_markup=get_dynamic_menu_admin_keyboard()
    )
    logging.info(f"Admin {message.from_user.id} yangi taom qo'shdi: #{item_id} {data['item_name']}")


# ─────────────────────────────────────────────
# ADMIN: Narx o'zgartirish
# ─────────────────────────────────────────────

async def admin_start_change_price(message: types.Message):
    """Narx o'zgartirish uchun taomlar ro'yxatini inline klaviatura bilan ko'rsatadi."""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q.")
        return

    items = await dm_get_all_items()
    if not items:
        await message.answer("⚠️ Menyu bo'sh. Avval taom qo'shing.")
        return

    markup = get_items_inline_keyboard(items, action="price")
    await message.answer(
        "💰 <b>Qaysi taomning narxini o'zgartirmoqchisiz?</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )


async def admin_select_item_for_price(call: types.CallbackQuery, state: FSMContext):
    """Inline tugmadan tanlangan taom ID sini saqlab, yangi narx so'raydi."""
    item_id = int(call.data.split("_")[2])  # dm_price_{id}
    item = await dm_get_item_by_id(item_id)

    if not item:
        await call.answer("Taom topilmadi.", show_alert=True)
        return

    await state.update_data(change_price_item_id=item_id)
    await DynamicMenuAdminStates.waiting_new_price.set()
    lang = await get_user_language(call.from_user.id)
    await call.message.edit_text(
        f"✅ Tanlangan: <b>{item['name']}</b>\n"
        f"{get_text('price_label', lang, price=item['price'])}\n\n"
        f"{get_text('admin_price_ask', lang)}\n"
        f"<i>Bekor qilish: /bekor</i>",
        parse_mode="HTML"
    )
    await call.answer()


async def admin_receive_new_price(message: types.Message, state: FSMContext):
    """Yangi narxni qabul qilib bazani yangilaydi."""
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_dynamic_menu_admin_keyboard())
        return

    try:
        new_price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Narx musbat son bo'lishi kerak:")
        return

    data = await state.get_data()
    item_id = data["change_price_item_id"]
    item = await dm_get_item_by_id(item_id)
    success = await dm_update_price(item_id, new_price)

    await state.finish()
    if success and item:
        lang = await get_user_language(message.from_user.id)
        await message.answer(
            f"✅ <b>{item['name']}</b> narxi yangilandi!\n"
            + get_text("admin_old_price", lang, old=item['price'], new=new_price),
            parse_mode="HTML",
            reply_markup=get_dynamic_menu_admin_keyboard()
        )
        logging.info(f"Admin {message.from_user.id} #{item_id} narxini {new_price} ga o'zgartirdi")
    else:
        await message.answer("❌ Xatolik yuz berdi.", reply_markup=get_dynamic_menu_admin_keyboard())


# ─────────────────────────────────────────────
# ADMIN: Taomni o'chirish
# ─────────────────────────────────────────────

async def admin_start_delete_item(message: types.Message):
    """O'chirish uchun taomlar ro'yxatini inline klaviatura bilan ko'rsatadi."""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q.")
        return

    items = await dm_get_all_items()
    if not items:
        await message.answer("⚠️ Menyu bo'sh.")
        return

    markup = get_items_inline_keyboard(items, action="delete")
    await message.answer(
        "🗑 <b>Qaysi taomni o'chirmoqchisiz?</b>\n"
        "<i>Diqqat: bu amalni ortga qaytarib bo'lmaydi!</i>",
        reply_markup=markup,
        parse_mode="HTML"
    )


async def admin_confirm_delete_item(call: types.CallbackQuery):
    """Tanlangan taomni bazadan o'chiradi."""
    item_id = int(call.data.split("_")[2])  # dm_delete_{id}
    item = await dm_get_item_by_id(item_id)

    if not item:
        await call.answer("Taom topilmadi.", show_alert=True)
        return

    success = await dm_delete_item(item_id)
    if success:
        await call.message.edit_text(
            f"✅ <b>{item['name']}</b> muvaffaqiyatli o'chirildi.",
            parse_mode="HTML"
        )
        logging.info(f"Admin {call.from_user.id} #{item_id} taomni o'chirdi")
    else:
        await call.message.edit_text("❌ O'chirishda xatolik yuz berdi.")
    await call.answer()


# ─────────────────────────────────────────────
# Callback: Bekor qilish
# ─────────────────────────────────────────────

async def admin_cancel_callback(call: types.CallbackQuery, state: FSMContext):
    """Inline 'Bekor qilish' tugmasi."""
    await state.finish()
    await call.message.edit_text("❌ Amal bekor qilindi.")
    await call.answer()


# ─────────────────────────────────────────────
# ADMIN MENYU: kategoriya → mahsulot (narx o'zgartirish)
# ─────────────────────────────────────────────

async def admin_show_category_products(call: types.CallbackQuery):
    """admin_cat_{id} — adminning kategoriya tanlashi."""
    if not _is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q.", show_alert=True)
        return

    from database.connection import get_db_pool
    from keyboards.product_keyboard import get_admin_product_markup

    category_id = int(call.data.split("_")[2])
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch("SELECT * FROM products WHERE category_id = $1 ORDER BY id", int(category_id))

    if not products:
        await call.answer("Bu kategoriyada mahsulotlar yo'q.", show_alert=True)
        return

    await call.message.delete()
    await _send_admin_product_page(call, products[0], category_id, 0, len(products))
    await call.answer()


async def admin_paginate_products(call: types.CallbackQuery):
    """admin_paginate_{cat_id}_{index} — admin mahsulot sahifalash."""
    if not _is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q.", show_alert=True)
        return

    from database.connection import get_db_pool

    parts = call.data.split("_")
    category_id = int(parts[2])
    index = int(parts[3])

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch("SELECT * FROM products WHERE category_id = $1 ORDER BY id", int(category_id))
    if not products or index < 0 or index >= len(products):
        await call.answer("Boshqa mahsulot yo'q.")
        return

    await _send_admin_product_page(call, products[index], category_id, index, len(products), is_edit=True)
    await call.answer()


async def admin_back_to_categories(call: types.CallbackQuery):
    """admin_back_to_cats — adminni kategoriyalar ro'yxatiga qaytarish."""
    if not _is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q.", show_alert=True)
        return

    from database.crud import get_categories
    from keyboards.product_keyboard import get_admin_categories_markup

    try:
        await call.message.delete()
    except Exception:
        pass

    categories = await get_categories()
    await call.message.answer(
        "🍽 <b>Menyu</b>\nQuyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_admin_categories_markup(categories),
        parse_mode="HTML"
    )
    await call.answer()


async def _send_admin_product_page(call, product, category_id, index, total, is_edit=False):
    """Admin mahsulot sahifasini yuboradi yoki tahrirlaydi."""
    from keyboards.product_keyboard import get_admin_product_markup

    # Chegirma va holat
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

    # Admin o'z tili bilan ko'rsin
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

    markup = get_admin_product_markup(product['id'], category_id, index, total, is_active=is_active, has_discount=has_discount)

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
    """Xavfsiz mahsulot yuborish — rasm xatosi bo'lsa matn yuboradi."""
    if product['image_url']:
        try:
            await message.answer_photo(photo=product['image_url'], caption=caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await message.answer(caption, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=markup, parse_mode="HTML")


async def admin_inline_price_start(call: types.CallbackQuery, state: FSMContext):
    """admin_price_{product_id} — narx o'zgartirish boshlash."""
    if not _is_admin(call.from_user.id):
        await call.answer("❌ Ruxsat yo'q.", show_alert=True)
        return

    from database.crud import get_product
    product_id = int(call.data.split("_")[2])
    product = await get_product(product_id)

    if not product:
        await call.answer("Mahsulot topilmadi.", show_alert=True)
        return

    await state.update_data(admin_price_product_id=product_id)
    await AdminProductStates.waiting_new_price_inline.set()
    lang = await get_user_language(call.from_user.id)
    await call.message.answer(
        f"✏️ <b>{product['name']}</b>\n"
        f"{get_text('price_label', lang, price=product['price'])}\n\n"
        f"{get_text('admin_price_ask', lang)}",
        parse_mode="HTML"
    )
    await call.answer()


async def admin_inline_price_receive(message: types.Message, state: FSMContext):
    """Yangi narxni qabul qilib bazada yangilaydi."""
    try:
        new_price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Faqat musbat son yozing:")
        return

    data = await state.get_data()
    product_id = data["admin_price_product_id"]

    from database.crud import get_product
    from database.connection import get_db_pool
    product = await get_product(product_id)

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE products SET price = $1 WHERE id = $2",
            new_price, product_id
        )

    await state.finish()
    lang = await get_user_language(message.from_user.id)
    await message.answer(
        f"✅ <b>{product['name']}</b> narxi yangilandi!\n"
        + get_text("admin_old_price", lang, old=product['price'], new=new_price),
        parse_mode="HTML"
    )
    logging.info(f"Admin {message.from_user.id} #{product_id} mahsulot narxini {new_price} ga o'zgartirdi")


# ─────────────────────────────────────────────
# Handler ro'yxatdan o'tkazish
# ─────────────────────────────────────────────

def register_dynamic_menu_handlers(dp: Dispatcher):

    # ── Admin menu / Menyuni ko'rish tugmalari ─────────────────────
    _ADMIN_MENU_TEXTS = ["🛠 Admin menu", "🛠 Admin menyu", "🛠 Меню админа", "🛠 Admin Menu"]
    dp.register_message_handler(
        user_show_dynamic_menu,
        lambda m: m.text in _ADMIN_MENU_TEXTS,
        state="*"
    )

    # ── Admin panel (Menyu boshqaruvi) ─────────────────────────────
    _MENU_MGMT_TEXTS = ["🛠 Menyu boshqaruvi", "🛠 Управление меню", "🛠 Menu Management"]
    dp.register_message_handler(
        admin_open_dynamic_panel,
        lambda m: m.text in _MENU_MGMT_TEXTS,
        state="*"
    )
    dp.register_message_handler(
        admin_back_from_dynamic_panel,
        Text(equals="⬅️ Orqaga"),
        state="*"
    )
    dp.register_message_handler(
        admin_view_dynamic_menu,
        Text(equals="📝 Menyuni ko'rish"),
        state="*"
    )

    # ── Taom qo'shish ──────────────────────────────────────────────
    dp.register_message_handler(
        admin_start_add_item,
        Text(equals="➕ Taom qo'shish"),
        state="*"
    )
    dp.register_message_handler(
        admin_receive_item_name,
        state=DynamicMenuAdminStates.waiting_item_name
    )
    dp.register_message_handler(
        admin_receive_item_price,
        state=DynamicMenuAdminStates.waiting_item_price
    )
    dp.register_message_handler(
        admin_receive_item_description,
        state=DynamicMenuAdminStates.waiting_item_description
    )

    # ── Narx o'zgartirish (menyu boshqaruvi) ──────────────────────
    dp.register_message_handler(
        admin_start_change_price,
        Text(equals="💰 Narx o'zgartirish"),
        state="*"
    )
    dp.register_callback_query_handler(
        admin_select_item_for_price,
        lambda c: c.data and c.data.startswith("dm_price_"),
        state="*"
    )
    dp.register_message_handler(
        admin_receive_new_price,
        state=DynamicMenuAdminStates.waiting_new_price
    )

    # ── O'chirish ──────────────────────────────────────────────────
    dp.register_message_handler(
        admin_start_delete_item,
        Text(equals="🗑 Taomni o'chirish"),
        state="*"
    )
    dp.register_callback_query_handler(
        admin_confirm_delete_item,
        lambda c: c.data and c.data.startswith("dm_delete_"),
        state="*"
    )

    # ── Bekor qilish callback ──────────────────────────────────────
    dp.register_callback_query_handler(
        admin_cancel_callback,
        lambda c: c.data == "dm_cancel",
        state="*"
    )

    # ── Admin menyu ichidan: kategoriya → mahsulot → narx ─────────
    dp.register_callback_query_handler(
        admin_show_category_products,
        lambda c: c.data and c.data.startswith("admin_cat_"),
        state="*"
    )
    dp.register_callback_query_handler(
        admin_paginate_products,
        lambda c: c.data and c.data.startswith("admin_paginate_"),
        state="*"
    )
    dp.register_callback_query_handler(
        admin_back_to_categories,
        lambda c: c.data == "admin_back_to_cats",
        state="*"
    )
    dp.register_callback_query_handler(
        admin_inline_price_start,
        lambda c: c.data and c.data.startswith("admin_price_"),
        state="*"
    )
    dp.register_message_handler(
        admin_inline_price_receive,
        state=AdminProductStates.waiting_new_price_inline
    )
