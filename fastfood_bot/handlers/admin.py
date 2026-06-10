import asyncio
import logging
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_ID
from keyboards.admin_keyboard import (
    get_admin_keyboard, get_order_status_keyboard,
    STATUS_LABELS, get_status_label
)
from utils.states import AdminStates, AddProductStates, AdminProductStates
from database.connection import get_db_pool
from database.crud import (
    get_categories, add_product, get_all_orders, get_order_by_id,
    get_order_items_detail, update_order_status, toggle_product_active,
    update_product_image, set_product_discount, remove_product_discount,
    get_today_stats, get_top_products, get_product, get_user_language
)
from utils.i18n import get_text


def _is_admin(user_id: int) -> bool:
    allowed = [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return str(user_id) in allowed


# ── /admin ───────────────────────────────────────────────────────────

async def cmd_admin(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    lang = await get_user_language(message.from_user.id)
    await message.answer("✅ Admin panel", reply_markup=get_admin_keyboard(lang))


# ── Statistika (kengaytirilgan) ──────────────────────────────────────

async def stats_handler(message: types.Message):
    if not _is_admin(message.from_user.id):
        return

    from database.crud import get_today_stats, get_top_products
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        orders_count = await conn.fetchval("SELECT COUNT(*) FROM orders")
        pending = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = $1", "pending")

    today_orders, today_revenue = await get_today_stats()
    top = await get_top_products(5)

    top_text = ""
    if top:
        for i, p in enumerate(top, 1):
            top_text += f"  {i}. {p['name']} — {p['total_qty']} ta\n"
    else:
        top_text = "  Ma'lumot yo'q\n"

    await message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{users_count}</b>\n"
        f"📦 Jami buyurtmalar: <b>{orders_count}</b>\n"
        f"⏳ Kutilayotgan: <b>{pending}</b>\n\n"
        f"📅 <b>Bugungi kun:</b>\n"
        f"  🛒 Buyurtmalar: <b>{today_orders}</b>\n"
        f"  💰 Tushum: <b>{today_revenue:,} so'm</b>\n\n"
        f"🏆 <b>Top mahsulotlar:</b>\n{top_text}",
        parse_mode="HTML"
    )


# ── Xabar tarqatish ─────────────────────────────────────────────────

async def start_broadcast(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    await AdminStates.broadcast_message.set()
    await message.answer("Xabar matnini yuboring (yoki rasmli xabar):")

async def send_broadcast(message: types.Message, state: FSMContext):
    text = message.text or message.caption
    photo = message.photo[-1].file_id if message.photo else None
    entities = message.entities or message.caption_entities
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")
    count = 0
    for i, user in enumerate(users):
        try:
            if photo:
                await message.bot.send_photo(
                    user['user_id'], photo, caption=text, parse_mode="HTML"
                )
            else:
                await message.bot.send_message(
                    user['user_id'], text, parse_mode="HTML"
                )
            count += 1
        except Exception:
            pass
        if (i + 1) % 20 == 0:
            await asyncio.sleep(1.0)
    await message.answer(f"✅ Xabar <b>{count}</b> ta foydalanuvchiga yuborildi.", parse_mode="HTML")
    await state.finish()


# ── Buyurtmalar paneli ───────────────────────────────────────────────

async def admin_orders(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    await _show_orders_list(message)

async def _show_orders_list(message, status_filter=None):
    orders = await get_all_orders(status=status_filter, limit=15)
    if not orders:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("⏳ Kutilayotgan", callback_data="adm_ordfilter_pending"),
            InlineKeyboardButton("🍳 Tayyorlanmoqda", callback_data="adm_ordfilter_preparing"),
        )
        await message.answer("📦 Buyurtmalar yo'q.", reply_markup=markup)
        return

    text = "📦 <b>Buyurtmalar</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    for o in orders:
        text_line = f"{get_status_label(o['status'], lang)} #{o['id']} | {o.get('full_name', '—') or '—'} | {o['total_amount']:,} so'm"
        markup.add(InlineKeyboardButton(text_line, callback_data=f"adm_order_{o['id']}"))

    markup.row(
    )
    markup.row(
        InlineKeyboardButton("📦 Barchasi", callback_data="adm_ordfilter_all"),
    )
    await message.answer(text, reply_markup=markup, parse_mode="HTML")

async def admin_order_filter(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    status = call.data.split("_")[2]
    try:
        await call.message.delete()
    except Exception:
        pass
    if status == "all":
        await _show_orders_list(call.message)
    else:
        await _show_orders_list(call.message, status_filter=status)
    await call.answer()

async def admin_order_detail(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    order_id = int(call.data.split("_")[2])
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi.", show_alert=True)
        return
    items = await get_order_items_detail(order_id)
    status = order['status'] or 'pending'
    created = order['created_at']
    date_str = created.strftime('%Y-%m-%d %H:%M') if hasattr(created, 'strftime') else str(created)[:16]

    items_text = ""
    for it in items:
        items_text += f"  ▫️ {it['name']} x {it['quantity']} = {it['price_at_time'] * it['quantity']:,} so'm\n"

    note = None
    try:
        note = order['note']
    except (KeyError, IndexError):
        pass
    note_text = f"\n📝 Izoh: <i>{note}</i>" if note else ""

    username_display = f"(@{order['username']})" if order.get('username') else ""
    phone_display = order['phone_number'] or '—'
    addr_display = order['delivery_address'] or '—'
    text = (
        f"📋 <b>Buyurtma #{order['id']}</b>\n\n"
        f"👤 {order.get('full_name', '—')} {username_display}\n"
        f"📅 {date_str}\n"
        f"Holat: {STATUS_LABELS.get(status, status)}\n"
        f"📍 {order['delivery_address'] or '—'}\n"
        f"📞 {order['phone_number'] or '—'}\n"
        f"{note_text}\n\n"
        f"🍛 <b>Tarkibi:</b>\n{items_text}\n"
        f"💰 <b>Jami: {order['total_amount']:,} so'm</b>"
    )
    lang = await get_user_language(call.from_user.id)
    markup = get_order_status_keyboard(order_id, status, lang)
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await call.answer()

async def admin_change_order_status(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    order_id = int(parts[2])
    new_status = parts[3]
    await update_order_status(order_id, new_status)
    await call.answer(f"✅ Holat o'zgartirildi: {STATUS_LABELS.get(new_status, new_status)}", show_alert=True)

    # Foydalanuvchiga xabar yuborish
    order = await get_order_by_id(order_id)
    if order:
        user_id = order['user_id']
        is_eat_in = False
        try:
            is_eat_in = order.get('delivery_type') == 'eat_in' or \
                        (order.get('delivery_address') and 'Stol raqami' in str(order.get('delivery_address', '')))
        except Exception:
            pass

        # Foydalanuvchi o'z tilida xabar olsin
        user_lang = await get_user_language(user_id)

        if is_eat_in:
            status_keys = {
                "preparing":  "order_preparing_eat_in",
                "delivering": "order_delivering_eat_in",
                "completed":  "order_completed_eat_in",
                "cancelled":  "order_cancelled_msg",
            }
        else:
            status_keys = {
                "preparing":  "order_preparing_delivery",
                "delivering": "order_delivering_delivery",
                "completed":  "order_completed_delivery",
                "cancelled":  "order_cancelled_msg",
            }
        key = status_keys.get(new_status)
        if key:
            msg = get_text(key, user_lang, id=order_id)
            try:
                await call.bot.send_message(user_id, msg, parse_mode="HTML")
            except Exception:
                pass

    # Sahifani yangilash
    call.data = f"adm_order_{order_id}"
    await admin_order_detail(call)

async def admin_orders_back(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    try:
        await call.message.delete()
    except Exception:
        pass
    await _show_orders_list(call.message)
    await call.answer()


# ── Mahsulot qo'shish (5 bosqich) ───────────────────────────────────

async def admin_start_add_product(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    categories = await get_categories()
    if not categories:
        await message.answer("⚠️ Kategoriyalar yo'q.")
        return
    markup = InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        markup.insert(InlineKeyboardButton(
            f"{cat['emoji'] or '🍽'} {cat['name']}",
            callback_data=f"adm_addprod_cat_{cat['id']}"
        ))
    markup.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_addprod_cancel"))
    await AddProductStates.waiting_category.set()
    await message.answer("➕ <b>Yangi mahsulot</b>\n\n1-qadam: Kategoriyani tanlang:", reply_markup=markup, parse_mode="HTML")

async def admin_addprod_category(call: types.CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split("_")[3])
    await state.update_data(category_id=cat_id)
    await AddProductStates.waiting_name.set()
    await call.message.edit_text("2-qadam: Mahsulot <b>nomini</b> yozing:\n<i>/bekor — bekor qilish</i>", parse_mode="HTML")
    await call.answer()

async def admin_addprod_name(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Nom kamida 2 harf. Qaytadan:")
        return
    await state.update_data(name=name)
    await AddProductStates.waiting_price.set()
    await message.answer(f"✅ Nom: <b>{name}</b>\n\n3-qadam: <b>Narxini</b> yozing (son, so'mda):", parse_mode="HTML")

async def admin_addprod_price(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0: raise ValueError
    except ValueError:
        await message.answer("⚠️ Musbat son yozing:")
        return
    await state.update_data(price=price)
    await AddProductStates.waiting_description.set()
    await message.answer(f"✅ Narx: <b>{price:,} so'm</b>\n\n4-qadam: <b>Tavsif</b> yozing (tire = o'tkazish):", parse_mode="HTML")

async def admin_addprod_description(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
    desc = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=desc)
    await AddProductStates.waiting_image.set()
    await message.answer("5-qadam: <b>Rasm</b> yuboring yoki URL yozing (tire = rasmsiz):", parse_mode="HTML")

async def admin_addprod_image(message: types.Message, state: FSMContext):
    if message.text and message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
    image_url = None
    if message.photo:
        image_url = message.photo[-1].file_id
    elif message.text and message.text.strip() != "-":
        image_url = message.text.strip()
    data = await state.get_data()
    pid = await add_product(data["category_id"], data["name"], data["price"], data.get("description",""), image_url)
    await state.finish()
    await message.answer(
        f"🎉 <b>Mahsulot qo'shildi!</b>\n\n🆔 {pid}\n🍽 {data['name']}\n💰 {data['price']:,} so'm\n🖼 {'✅' if image_url else '—'}",
        parse_mode="HTML", reply_markup=get_admin_keyboard()
    )
    logging.info(f"Admin {message.from_user.id} mahsulot qo'shdi #{pid}")

async def admin_addprod_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text("❌ Bekor qilindi.")
    await call.answer()


# ── Admin menyu: rasm almashish ──────────────────────────────────────

async def admin_image_start(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split("_")[2])
    await state.update_data(admin_image_product_id=pid)
    await AdminProductStates.waiting_new_image.set()
    await call.message.answer("🖼 Yangi rasm yuboring yoki URL yozing:\n<i>/bekor — bekor qilish</i>", parse_mode="HTML")
    await call.answer()

async def admin_image_receive(message: types.Message, state: FSMContext):
    if message.text and message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.")
        return
    image_url = None
    if message.photo:
        image_url = message.photo[-1].file_id
    elif message.text:
        image_url = message.text.strip()
    if not image_url:
        await message.answer("⚠️ Rasm yoki URL yuboring:")
        return
    data = await state.get_data()
    pid = data["admin_image_product_id"]
    await update_product_image(pid, image_url)
    await state.finish()
    await message.answer("✅ Rasm yangilandi!", parse_mode="HTML")
    logging.info(f"Admin {message.from_user.id} #{pid} rasmini yangiladi")


# ── Admin menyu: chegirma ────────────────────────────────────────────

async def admin_discount_start(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split("_")[2])
    product = await get_product(pid)
    if not product:
        await call.answer("Topilmadi.", show_alert=True)
        return

    old_price = None
    try:
        old_price = product['old_price']
    except (KeyError, IndexError):
        pass

    if old_price and old_price > product['price']:
        await remove_product_discount(pid)
        await call.answer("✅ Chegirma olib tashlandi!", show_alert=True)
        return

    await state.update_data(admin_discount_product_id=pid)
    await AdminProductStates.waiting_discount_price.set()
    await call.message.answer(
        f"🏷 <b>{product['name']}</b>\nHozirgi narx: <b>{product['price']:,} so'm</b>\n\n"
        f"Chegirma narxini yozing (so'mda):\n<i>/bekor — bekor qilish</i>",
        parse_mode="HTML"
    )
    await call.answer()

async def admin_discount_receive(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.")
        return
    try:
        new_price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if new_price <= 0: raise ValueError
    except ValueError:
        await message.answer("⚠️ Musbat son yozing:")
        return
    data = await state.get_data()
    pid = data["admin_discount_product_id"]
    await set_product_discount(pid, new_price)
    await state.finish()
    await message.answer(f"✅ Chegirma qo'yildi! Yangi narx: <b>{new_price:,} so'm</b>", parse_mode="HTML")
    logging.info(f"Admin {message.from_user.id} #{pid} chegirma: {new_price}")


# ── Admin menyu: yashirish/ko'rsatish ────────────────────────────────

async def admin_toggle_product(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split("_")[2])
    new_status = await toggle_product_active(pid)
    if new_status is not None:
        status_text = "✅ Ko'rsatildi (faol)" if new_status else "🙈 Yashirildi (nofaol)"
        await call.answer(status_text, show_alert=True)
    else:
        await call.answer("Xatolik.", show_alert=True)


# ── Asosiy menuga qaytish ────────────────────────────────────────────

async def admin_back_to_main(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.finish()
    from keyboards.main_menu import get_admin_main_menu
    lang = await get_user_language(message.from_user.id)
    await message.answer("✅", reply_markup=get_admin_main_menu(lang))


# ── Promo kodlar ─────────────────────────────────────────────────────

async def admin_promo_list(message: types.Message):
    """Promo kodlar ro'yxati."""
    if not _is_admin(message.from_user.id):
        return
    from database.crud import get_all_promo_codes
    codes = await get_all_promo_codes()
    if not codes:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ Yangi kod yaratish", callback_data="promo_create"))
        await message.answer("🎟 Promo kodlar yo'q.", reply_markup=markup)
        return
    text = "🎟 <b>Promo kodlar:</b>\n\n"
    markup = InlineKeyboardMarkup(row_width=1)
    for c in codes:
        uses = f"{c['used_count']}/{c['max_uses']}" if c['max_uses'] > 0 else f"{c['used_count']}/∞"
        status = "✅" if c['is_active'] else "❌"
        text += f"{status} <code>{c['code']}</code> — {c['discount_percent']}% | {uses}\n"
        markup.add(InlineKeyboardButton(f"🗑 {c['code']} ni o'chirish", callback_data=f"promo_del_{c['code']}"))
    markup.add(InlineKeyboardButton("➕ Yangi kod yaratish", callback_data="promo_create"))
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def admin_promo_create_start(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    from utils.states import PromoCodeStates
    await PromoCodeStates.waiting_code.set()
    await call.message.answer("🎟 Promo kod nomini yozing (masalan: YANGI2026):\n<i>/bekor — bekor qilish</i>", parse_mode="HTML")
    await call.answer()


async def admin_promo_code_name(message: types.Message, state: FSMContext):
    from utils.states import PromoCodeStates
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.")
        return
    code = message.text.strip().upper()
    if len(code) < 3:
        await message.answer("⚠️ Kod kamida 3 harf bo'lishi kerak.")
        return
    await state.update_data(promo_code=code)
    await PromoCodeStates.waiting_discount.set()
    await message.answer(f"Kod: <b>{code}</b>\n\nChegirma foizini yozing (1-100):", parse_mode="HTML")


async def admin_promo_discount(message: types.Message, state: FSMContext):
    from utils.states import PromoCodeStates
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.")
        return
    try:
        pct = int(message.text.strip())
        if pct < 1 or pct > 100:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ 1 dan 100 gacha son yozing.")
        return
    await state.update_data(discount_percent=pct)
    await PromoCodeStates.waiting_max_uses.set()
    await message.answer(f"Chegirma: <b>{pct}%</b>\n\nNecha marta ishlatilishi mumkin? (0 = cheksiz)", parse_mode="HTML")


async def admin_promo_max_uses(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.")
        return
    try:
        max_uses = int(message.text.strip())
        if max_uses < 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ 0 yoki musbat son yozing.")
        return
    data = await state.get_data()
    from database.crud import create_promo_code
    await create_promo_code(data['promo_code'], data['discount_percent'], max_uses)
    await state.finish()
    uses_text = f"{max_uses} marta" if max_uses > 0 else "cheksiz"
    await message.answer(
        f"✅ <b>Promo kod yaratildi!</b>\n\n"
        f"🎟 Kod: <code>{data['promo_code']}</code>\n"
        f"💰 Chegirma: <b>{data['discount_percent']}%</b>\n"
        f"🔢 Ishlatish: <b>{uses_text}</b>",
        parse_mode="HTML"
    )


async def admin_promo_delete(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    code = call.data.split("_")[2]
    from database.crud import delete_promo_code
    await delete_promo_code(code)
    await call.answer(f"🗑 {code} o'chirildi!", show_alert=True)
    try:
        await call.message.delete()
    except Exception:
        pass


# ── CSV Hisobot ──────────────────────────────────────────────────────

async def admin_csv_export(message: types.Message):
    """Buyurtmalarni CSV faylda yuborish."""
    if not _is_admin(message.from_user.id):
        return
    from database.crud import get_orders_for_export
    import csv
    import io
    import os

    orders = await get_orders_for_export()
    if not orders:
        await message.answer("📥 Buyurtmalar yo'q.")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Mijoz", "Telefon", "Summa", "Turi", "Manzil", "Izoh", "Holat", "Sana"])
    for o in orders:
        created = o['created_at']
        date_str = created.strftime('%Y-%m-%d %H:%M') if hasattr(created, 'strftime') else str(created)[:16]
        d_type = "Shu yerda" if o.get('delivery_type') == 'eat_in' else "Yetkazib berish"
        writer.writerow([
            o['id'],
            o['full_name'] or '—',
            o.get('order_phone') or o.get('user_phone') or '—',
            o['total_amount'],
            d_type,
            o['delivery_address'] or '—',
            o.get('note') or '—',
            STATUS_LABELS.get(o['status'] or 'pending', o['status']),
            date_str
        ])
    
    csv_bytes = output.getvalue().encode('utf-8-sig')  # Excel uchun BOM
    doc = io.BytesIO(csv_bytes)
    doc.name = "buyurtmalar_hisobot.csv"
    
    await message.answer_document(doc, caption=f"📥 <b>Buyurtmalar hisoboti</b>\n{len(orders)} ta buyurtma", parse_mode="HTML")


# ── Handlerlarni ro'yxatdan o'tkazish ────────────────────────────────

def register_admin_handlers(dp: Dispatcher):
    from utils.states import PromoCodeStates

    _STATS_TEXTS   = ["📊 Statistika", "📊 Статистика", "📊 Statistics"]
    _BCAST_TEXTS   = ["📢 Xabar tarqatish", "📢 Рассылка", "📢 Broadcast"]
    _BACK_TEXTS    = ["⬅️ Asosiy menu", "⬅️ Главное меню", "⬅️ Main Menu"]
    _ORDERS_TEXTS  = ["📦 Buyurtmalar", "📦 Заказы", "📦 Orders"]
    _ADDPROD_TEXTS = ["➕ Mahsulot qo'shish", "➕ Добавить продукт", "➕ Add Product"]
    _PROMO_TEXTS   = ["🎟 Promo kodlar", "🎟 Промо-коды", "🎟 Promo Codes"]
    _CSV_TEXTS     = ["📥 Hisobot (CSV)", "📥 Отчёт (CSV)", "📥 Report (CSV)"]

    dp.register_message_handler(cmd_admin, commands=['admin'])
    dp.register_message_handler(stats_handler,   lambda m: m.text in _STATS_TEXTS)
    dp.register_message_handler(start_broadcast, lambda m: m.text in _BCAST_TEXTS)
    dp.register_message_handler(send_broadcast, state=AdminStates.broadcast_message, content_types=types.ContentTypes.ANY)
    dp.register_message_handler(admin_back_to_main, lambda m: m.text in _BACK_TEXTS, state="*")

    # Buyurtmalar
    dp.register_message_handler(admin_orders, lambda m: m.text in _ORDERS_TEXTS, state="*")
    dp.register_callback_query_handler(admin_order_detail, lambda c: c.data and c.data.startswith("adm_order_") and not c.data.startswith("adm_ordstatus_") and not c.data.startswith("adm_ordfilter_"), state="*")
    dp.register_callback_query_handler(admin_change_order_status, lambda c: c.data and c.data.startswith("adm_ordstatus_"), state="*")
    dp.register_callback_query_handler(admin_order_filter, lambda c: c.data and c.data.startswith("adm_ordfilter_"), state="*")
    dp.register_callback_query_handler(admin_orders_back, text="adm_orders_back", state="*")

    # Mahsulot qo'shish
    dp.register_message_handler(admin_start_add_product, lambda m: m.text in _ADDPROD_TEXTS, state="*")
    dp.register_callback_query_handler(admin_addprod_category, lambda c: c.data and c.data.startswith("adm_addprod_cat_"), state=AddProductStates.waiting_category)
    dp.register_callback_query_handler(admin_addprod_cancel, lambda c: c.data == "adm_addprod_cancel", state="*")
    dp.register_message_handler(admin_addprod_name, state=AddProductStates.waiting_name)
    dp.register_message_handler(admin_addprod_price, state=AddProductStates.waiting_price)
    dp.register_message_handler(admin_addprod_description, state=AddProductStates.waiting_description)
    dp.register_message_handler(admin_addprod_image, content_types=[types.ContentType.PHOTO, types.ContentType.TEXT], state=AddProductStates.waiting_image)

    # Rasm almashish
    dp.register_callback_query_handler(admin_image_start, lambda c: c.data and c.data.startswith("admin_image_"), state="*")
    dp.register_message_handler(admin_image_receive, content_types=[types.ContentType.PHOTO, types.ContentType.TEXT], state=AdminProductStates.waiting_new_image)

    # Chegirma
    dp.register_callback_query_handler(admin_discount_start, lambda c: c.data and c.data.startswith("admin_discount_"), state="*")
    dp.register_message_handler(admin_discount_receive, state=AdminProductStates.waiting_discount_price)

    # Yashirish
    dp.register_callback_query_handler(admin_toggle_product, lambda c: c.data and c.data.startswith("admin_toggle_"), state="*")

    # Promo kodlar
    dp.register_message_handler(admin_promo_list, lambda m: m.text in _PROMO_TEXTS, state="*")
    dp.register_callback_query_handler(admin_promo_create_start, text="promo_create", state="*")
    dp.register_message_handler(admin_promo_code_name, state=PromoCodeStates.waiting_code)
    dp.register_message_handler(admin_promo_discount, state=PromoCodeStates.waiting_discount)
    dp.register_message_handler(admin_promo_max_uses, state=PromoCodeStates.waiting_max_uses)
    dp.register_callback_query_handler(admin_promo_delete, lambda c: c.data and c.data.startswith("promo_del_"), state="*")

    # CSV eksport
    dp.register_message_handler(admin_csv_export, lambda m: m.text in _CSV_TEXTS, state="*")

