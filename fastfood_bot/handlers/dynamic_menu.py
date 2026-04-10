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
from utils.states import DynamicMenuAdminStates


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
    Har qanday foydalanuvchi "📋 Dinamik Menyu" tugmasini bosganida
    eng so'nggi narxlar bilan menyu ko'rsatiladi.
    """
    items = await dm_get_all_items()
    text = format_menu_text(items)
    await message.answer(text, parse_mode="HTML")


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
    await message.answer("Admin paneliga qaytdingiz.", reply_markup=get_admin_main_menu())


# ─────────────────────────────────────────────
# ADMIN: Admin panelidan menyuni ko'rish
# ─────────────────────────────────────────────

async def admin_view_dynamic_menu(message: types.Message):
    """Admin '📝 Menyuni ko'rish' — mijozlardagi kabi rasm+nom+narx ko'rinishida."""
    if not _is_admin(message.from_user.id):
        await message.answer("❌ Ruxsat yo'q.")
        return

    from database.crud import get_categories, get_products_by_category

    categories = await get_categories()
    if not categories:
        await message.answer("⚠️ Kategoriyalar topilmadi.", reply_markup=get_dynamic_menu_admin_keyboard())
        return

    await message.answer(
        "🛠 <b>Admin — Menyu ko'rinishi</b>\n"
        "Quyida barcha kategoriya va mahsulotlar — rasm, narx bilan:",
        parse_mode="HTML",
        reply_markup=get_dynamic_menu_admin_keyboard()
    )

    for cat in categories:
        await message.answer(
            f"{cat['emoji']} <b>{cat['name']}</b>",
            parse_mode="HTML"
        )

        products = await get_products_by_category(cat['id'])
        if not products:
            await message.answer("  — mahsulotlar yo'q")
            continue

        for p in products:
            caption = (
                f"🍽 <b>{p['name']}</b>\n"
                f"📝 {p['description'] or '—'}\n"
                f"💰 <b>{p['price']:,} so'm</b>"
            )
            if p['image_url']:
                try:
                    await message.answer_photo(
                        photo=p['image_url'],
                        caption=caption,
                        parse_mode="HTML"
                    )
                except Exception:
                    await message.answer(caption, parse_mode="HTML")
            else:
                await message.answer(caption, parse_mode="HTML")


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
    await message.answer(
        f"✅ Narxi: <b>{price:,} so'm</b>\n\n"
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
    await message.answer(
        f"🎉 <b>Taom muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🆔 ID: <b>{item_id}</b>\n"
        f"🍽 Nomi: <b>{data['item_name']}</b>\n"
        f"💰 Narxi: <b>{data['item_price']:,} so'm</b>\n"
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
    await call.message.edit_text(
        f"✅ Tanlangan: <b>{item['name']}</b>\n"
        f"Hozirgi narxi: <b>{item['price']:,} so'm</b>\n\n"
        f"Yangi narxni yozing (so'mda):\n"
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
        await message.answer(
            f"✅ <b>{item['name']}</b> narxi yangilandi!\n"
            f"Eski narxi: <s>{item['price']:,} so'm</s>\n"
            f"Yangi narxi: <b>{new_price:,} so'm</b>",
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
# Handler ro'yxatdan o'tkazish
# ─────────────────────────────────────────────

def register_dynamic_menu_handlers(dp: Dispatcher):
    """
    Barcha dinamik menyu handlerlarini Dispatcher ga ro'yxatdan o'tkazadi.
    Boshqa handlerlarga hech qanday ta'siri yo'q.
    """

    # ── Foydalanuvchi ──────────────────────────────────────────────
    dp.register_message_handler(
        user_show_dynamic_menu,
        Text(equals="📋 Dinamik Menyu"),
        state="*"
    )

    # ── Admin panel ────────────────────────────────────────────────
    dp.register_message_handler(
        admin_open_dynamic_panel,
        Text(equals="🛠 Menyu boshqaruvi"),
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

    # ── Narx o'zgartirish ──────────────────────────────────────────
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
