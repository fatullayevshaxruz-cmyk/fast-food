import asyncio
import csv
import io
import logging
import random
import time
from datetime import datetime, date, timedelta
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_ID, WORKING_HOURS_START, WORKING_HOURS_END, COURIER_PHONE
from keyboards.admin_keyboard import (
    get_admin_keyboard, get_order_status_keyboard,
    STATUS_LABELS, get_status_label
)
from utils.states import AdminStates, AddProductStates, AdminProductStates, PromoCodeStates
from database.connection import get_db_pool
from database.crud import (
    get_categories, add_product, get_all_orders, get_order_by_id,
    get_order_items_detail, update_order_status, toggle_product_active,
    update_product_image, set_product_discount, remove_product_discount,
    get_today_stats, get_top_products, get_product, get_user_language,
    get_product_name, clear_cache, get_all_promo_codes, create_promo_code,
    delete_promo_code, toggle_promo_code, get_orders_for_export
)
from utils.i18n import get_text


def _is_admin(user_id: int) -> bool:
    if not ADMIN_ID:
        return False
    allowed = [a.strip() for a in ADMIN_ID.split(",") if a.strip()]
    return str(user_id) in allowed


def _progress_bar(current: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "░" * length + " 0%"
    ratio = min(1.0, max(0.0, current / total))
    filled = int(round(ratio * length))
    pct = int(round(ratio * 100))
    return ("▓" * filled) + ("░" * (length - filled)) + f" {pct}%"


def _uz_now_str() -> tuple:
    now_uz = datetime.utcnow() + timedelta(hours=5)
    is_open = WORKING_HOURS_START <= now_uz.hour < WORKING_HOURS_END
    status_badge = "🟢 Kafe ochiq" if is_open else "🔴 Kafe yopiq"
    return now_uz.strftime("%d.%m.%Y %H:%M"), status_badge


# ══════════════════════════════════════════════════════════════════════
# 0. /admin — KREATIV ADMIN BOSHQARUV MARKAZI
# ══════════════════════════════════════════════════════════════════════

async def _build_admin_dashboard_text() -> str:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        pending_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'pending'") or 0
        prep_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'preparing'") or 0
        deliv_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'delivering'") or 0
        promos_cnt = await conn.fetchval("SELECT COUNT(*) FROM promo_codes WHERE is_active != 0") or 0

    today_orders, today_revenue = await get_today_stats()
    time_str, cafe_badge = _uz_now_str()

    return (
        f"👑 <b>DARXAN BURGER — ADMIN BOSHQARUV MARKAZI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 Toshkent vaqti: <b>{time_str}</b> | {cafe_badge}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ <b>JONLI PULS (BUGUN):</b>\n"
        f"  🛒 Bugungi buyurtmalar: <b>{today_orders} ta</b>\n"
        f"  💰 Bugungi tushum: <b>{today_revenue:,} so'm</b>\n"
        f"  👥 Jami mijozlar: <b>{users_count} nafar</b>\n"
        f"  🎟 Faol promokodlar: <b>{promos_cnt} ta</b>\n\n"
        f"🚦 <b>FAOL BUYURTMALAR HOLATI:</b>\n"
        f"  ⏳ Kutilmoqda: <b>{pending_cnt}</b> | 🍳 Oshxonada: <b>{prep_cnt}</b> | 🛵 Yo'lda: <b>{deliv_cnt}</b>\n\n"
        f"🧭 <b>BO'LIMLAR YO'RIQNOMASI:</b>\n"
        f"  📦 <b>Buyurtmalar</b> — barcha buyurtmalarni filtrlash va boshqarish\n"
        f"  📊 <b>Statistika</b> — chuqur moliyaviy tahlil, reyting va TOP-5 taomlar\n"
        f"  📢 <b>Xabar tarqatish</b> — mijozlarga kreativ reklama / aksiya yuborish\n"
        f"  ➕ <b>Mahsulot qo'shish</b> — yangi taomni 5 qadamda menyuga kiritish\n"
        f"  🎟 <b>Promo kodlar</b> — kuponlar yaratish, muzlatish va e'lon qilish\n"
        f"  📥 <b>Hisobot (CSV)</b> — Excel/CSV buxgalteriya hisobotlari va mijozlar bazasi\n"
        f"  🛠 <b>Admin menyu / Menyu boshqaruvi</b> — narx, rasm va chegirmalar"
    )


def _get_admin_dashboard_inline() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔥 Faol buyurtmalar", callback_data="adm_ordfilter_active"),
        InlineKeyboardButton("📊 Tezkor statistika", callback_data="adm_stats_refresh"),
    )
    markup.add(
        InlineKeyboardButton("🎲 Tezkor VIP Promo yaratish", callback_data="promo_random"),
        InlineKeyboardButton("🔄 Panelni yangilash", callback_data="adm_dash_refresh"),
    )
    return markup


async def cmd_admin(message: types.Message, state: FSMContext = None):
    if not _is_admin(message.from_user.id):
        return
    if state:
        await state.finish()
    lang = await get_user_language(message.from_user.id)
    text = await _build_admin_dashboard_text()
    await message.answer(
        text,
        reply_markup=get_admin_keyboard(lang),
        parse_mode="HTML"
    )
    await message.answer(
        "👇 <i>Tezkor amallar:</i>",
        reply_markup=_get_admin_dashboard_inline(),
        parse_mode="HTML"
    )


async def admin_dash_refresh_cb(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    text = await _build_admin_dashboard_text()
    try:
        await call.message.edit_text(
            text + "\n\n👇 <i>Tezkor amallar:</i>",
            reply_markup=_get_admin_dashboard_inline(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await call.answer("🔄 Ma'lumotlar yangilandi!")


# ══════════════════════════════════════════════════════════════════════
# 1. 📊 STATISTIKA — KREATIV BIZNES ANALITIKA VA REYTING PANELI
# ══════════════════════════════════════════════════════════════════════

async def _build_creative_stats_text() -> tuple:
    pool = await get_db_pool()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    month_ago = (date.today() - timedelta(days=30)).isoformat()

    async with pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        orders_count = await conn.fetchval("SELECT COUNT(*) FROM orders") or 0
        total_revenue = await conn.fetchval(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != 'cancelled'"
        ) or 0

        pending_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'pending'") or 0
        prep_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'preparing'") or 0
        deliv_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'delivering'") or 0
        comp_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'completed'") or 0
        canc_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'cancelled'") or 0

        week_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE created_at >= $1 AND status != 'cancelled'", week_ago
        ) or 0
        week_rev = await conn.fetchval(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE created_at >= $1 AND status != 'cancelled'", week_ago
        ) or 0

        month_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE created_at >= $1 AND status != 'cancelled'", month_ago
        ) or 0
        month_rev = await conn.fetchval(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE created_at >= $1 AND status != 'cancelled'", month_ago
        ) or 0

        dlv_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE delivery_type = 'delivery'"
        ) or 0
        eatin_orders = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE delivery_type = 'eat_in'"
        ) or 0

        try:
            avg_rating = await conn.fetchval("SELECT AVG(rating) FROM order_ratings")
            ratings_cnt = await conn.fetchval("SELECT COUNT(*) FROM order_ratings") or 0
        except Exception:
            avg_rating, ratings_cnt = None, 0

    today_orders, today_revenue = await get_today_stats()
    top = await get_top_products(5)

    valid_orders = max(1, orders_count - canc_cnt)
    avg_check = int(total_revenue / valid_orders) if orders_count > 0 else 0

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    top_text = ""
    if top:
        for i, p in enumerate(top):
            p_d = dict(p)
            medal = medals[i] if i < len(medals) else "▫️"
            qty = p_d.get("total_qty") or 0
            rev = p_d.get("total_sum") or 0
            rev_str = f" ({rev:,} so'm)" if rev else ""
            top_text += f"  {medal} <b>{p_d['name']}</b> — {qty} dona{rev_str}\n"
    else:
        top_text = "  <i>Hozircha sotuvlar tarixi yo'q</i>\n"

    rating_str = f"⭐ <b>{avg_rating:.1f} / 5.0</b> ({ratings_cnt} ta baho)" if avg_rating else "⭐ <i>Hali baholanmagan</i>"
    dlv_bar = _progress_bar(dlv_orders, max(1, orders_count), 10)
    comp_bar = _progress_bar(comp_cnt, max(1, orders_count), 10)

    text = (
        f"📊 <b>DARXAN BURGER — BIZNES ANALITIKA MARKAZI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Jami mijozlar: <b>{users_count:,} nafar</b>\n"
        f"📦 Jami buyurtmalar: <b>{orders_count:,} ta</b>\n"
        f"💎 Umumiy oborot: <b>{total_revenue:,} so'm</b>\n"
        f"🧾 O'rtacha chek: <b>{avg_check:,} so'm</b>\n"
        f"🌟 Mijozlar mamnuniyati: {rating_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 <b>DAVRLAR BO'YICHA DAROMAD:</b>\n"
        f"  ☀️ <b>Bugun:</b> {today_orders} ta buyurtma — <b>{today_revenue:,} so'm</b>\n"
        f"  📆 <b>Oxirgi 7 kun:</b> {week_orders} ta — <b>{week_rev:,} so'm</b>\n"
        f"  🗓 <b>Oxirgi 30 kun:</b> {month_orders} ta — <b>{month_rev:,} so'm</b>\n\n"
        f"🚦 <b>BUYURTMALAR HOLATI:</b>\n"
        f"  ⏳ Kutilmoqda: <b>{pending_cnt}</b> | 🍳 Tayyorlanmoqda: <b>{prep_cnt}</b>\n"
        f"  🛵 Yetkazilmoqda: <b>{deliv_cnt}</b> | ✅ Tugallangan: <b>{comp_cnt}</b> | ❌ Bekor: <b>{canc_cnt}</b>\n"
        f"  📈 Muvaffaqiyat darajasi: <code>{comp_bar}</code>\n\n"
        f"🛵 <b>YETKAZIB BERISH ULUSHI:</b>\n"
        f"  🛵 Yetkazish: <b>{dlv_orders}</b> | 🍽 Shu yerda: <b>{eatin_orders}</b>\n"
        f"  📊 Nisbat: <code>{dlv_bar}</code>\n\n"
        f"🏆 <b>TOP-5 XIT TAOMLAR (BESTSELLERLAR):</b>\n"
        f"{top_text}"
    )

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔄 Yangilash", callback_data="adm_stats_refresh"),
        InlineKeyboardButton("💬 Mijozlar fikrlari", callback_data="adm_stats_feedbacks"),
    )
    markup.add(
        InlineKeyboardButton("📥 CSV Hisobotni yuklash", callback_data="csv_exp_all"),
    )
    return text, markup


async def stats_handler(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    text, markup = await _build_creative_stats_text()
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def admin_stats_refresh_cb(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    text, markup = await _build_creative_stats_text()
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await call.answer("📊 Statistika yangilandi!")


async def admin_stats_feedbacks_cb(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                "SELECT r.*, u.full_name FROM order_ratings r "
                "LEFT JOIN users u ON r.user_id = u.user_id "
                "ORDER BY r.created_at DESC LIMIT 10"
            )
        except Exception:
            rows = []

    if not rows:
        await call.answer("ℹ️ Hozircha mijozlardan izohli baholar kelib tushmagan.", show_alert=True)
        return

    text = "💬 <b>SO'NGGI 10 TA MIJOZ BAHOSI VA FIKRLARI:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for r in rows:
        rd = dict(r)
        stars = "⭐" * int(rd.get("rating") or 5)
        name = rd.get("full_name") or "Mijoz"
        comment = rd.get("comment") or "<i>Izoh qoldirilmagan</i>"
        oid = rd.get("order_id") or "—"
        text += f"🧾 <b>Buyurtma #{oid}</b> | 👤 {name}\n{stars}\n💭 {comment}\n\n"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Statistikaga qaytish", callback_data="adm_stats_refresh"))
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await call.answer()


# ══════════════════════════════════════════════════════════════════════
# 2. 📢 XABAR TARQATISH — KREATIV MARKETING VA E'LONLAR STUDIYASI
# ══════════════════════════════════════════════════════════════════════

async def start_broadcast(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users") or 0

    await AdminStates.broadcast_message.set()
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_bcast_cancel"))

    await message.answer(
        f"📢 <b>DARXAN BURGER — MARKETING VA E'LONLAR STUDIYASI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Qabul qiluvchilar auditoriyasi: <b>{users_count} nafar mijoz</b>\n\n"
        f"✨ <b>Qo'llab-quvvatlanadigan formatlar:</b>\n"
        f"  • 📝 Oddiy yoki HTML formatdagi matn\n"
        f"  • 🖼 Rasm + chiroyli izoh (caption)\n"
        f"  • 🎥 Video yoki GIF animatsiya\n"
        f"  • 🎙 Ovozli xabar (Voice)\n\n"
        f"💡 <i>Xabaringizni hozir yuboring va u barcha mijozlarga darhol yetkaziladi!</i>\n"
        f"<i>Bekor qilish uchun pastdagi tugmani bosing yoki /bekor deb yozing.</i>",
        reply_markup=markup,
        parse_mode="HTML"
    )


async def cancel_broadcast_cb(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    await state.finish()
    try:
        await call.message.edit_text("❌ <b>Xabar tarqatish bekor qilindi.</b>", parse_mode="HTML")
    except Exception:
        pass
    await call.answer("Bekor qilindi")


async def send_broadcast(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.finish()
        return

    if message.text and message.text.strip().lower() in ("/bekor", "/cancel", "⬅️ asosiy menu", "⬅️ главное меню", "⬅️ main menu"):
        await state.finish()
        lang = await get_user_language(message.from_user.id)
        await message.answer("❌ <b>Xabar tarqatish bekor qilindi.</b>", reply_markup=get_admin_keyboard(lang), parse_mode="HTML")
        return

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")

    total_users = len(users)
    status_msg = await message.answer(
        f"🚀 <b>Xabar tarqatish boshlandi...</b>\n"
        f"👥 Jami auditoriya: <b>{total_users} ta</b>",
        parse_mode="HTML"
    )

    start_ts = time.time()
    sent_count = 0
    failed_count = 0

    text = message.html_text or message.caption or message.text or ""
    photo = message.photo[-1].file_id if message.photo else None
    video = message.video.file_id if message.video else None
    voice = message.voice.file_id if message.voice else None

    for i, user in enumerate(users):
        uid = user['user_id']
        try:
            if photo:
                await message.bot.send_photo(uid, photo, caption=text, parse_mode="HTML")
            elif video:
                await message.bot.send_video(uid, video, caption=text, parse_mode="HTML")
            elif voice:
                await message.bot.send_voice(uid, voice, caption=text, parse_mode="HTML")
            else:
                await message.bot.send_message(uid, text, parse_mode="HTML")
            sent_count += 1
        except Exception:
            failed_count += 1

        if (i + 1) % 20 == 0:
            await asyncio.sleep(0.8)

    elapsed = round(time.time() - start_ts, 1)
    bar = _progress_bar(sent_count, max(1, total_users), 10)
    await state.finish()

    report_text = (
        f"✅ <b>XABAR TARQATISH MUVAFFAQIYATLI YAKUNLANDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Natija: <code>{bar}</code>\n"
        f"✅ Yetkazildi: <b>{sent_count} nafar mijozga</b>\n"
        f"🚫 Yetib bormadi (bloklagan): <b>{failed_count} ta</b>\n"
        f"⏱ Sarflangan vaqt: <b>{elapsed} soniya</b>"
    )
    try:
        await status_msg.edit_text(report_text, parse_mode="HTML")
    except Exception:
        await message.answer(report_text, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════
# 3. 📦 BUYURTMALAR — KREATIV BUYURTMALAR BOSHQARUV PANELI
# ══════════════════════════════════════════════════════════════════════

async def admin_orders(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    await _show_orders_list(message)


async def _show_orders_list(message, status_filter=None):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        pending_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'pending'") or 0
        prep_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'preparing'") or 0
        deliv_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'delivering'") or 0
        comp_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'completed'") or 0
        canc_cnt = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status = 'cancelled'") or 0

        if status_filter == "active":
            orders = await conn.fetch(
                "SELECT o.*, u.full_name, u.username FROM orders o "
                "LEFT JOIN users u ON o.user_id = u.user_id "
                "WHERE o.status IN ('pending', 'preparing', 'delivering') "
                "ORDER BY o.created_at DESC LIMIT 20"
            )
        elif status_filter:
            orders = await get_all_orders(status=status_filter, limit=20)
        else:
            orders = await get_all_orders(status=None, limit=20)

    active_total = pending_cnt + prep_cnt + deliv_cnt
    filter_titles = {
        None: "📦 BARCHA BUYURTMALAR",
        "active": f"🔥 FAOL BUYURTMALAR ({active_total})",
        "pending": f"⏳ KUTILAYOTGAN BUYURTMALAR ({pending_cnt})",
        "preparing": f"🍳 TAYYORLANAYOTGAN BUYURTMALAR ({prep_cnt})",
        "delivering": f"🛵 YETKAZILAYOTGAN BUYURTMALAR ({deliv_cnt})",
        "completed": f"✅ TUGALLANGAN BUYURTMALAR ({comp_cnt})",
        "cancelled": f"❌ BEKOR QILINGAN BUYURTMALAR ({canc_cnt})",
    }
    title = filter_titles.get(status_filter, "📦 BUYURTMALAR")

    markup = InlineKeyboardMarkup(row_width=2)

    if orders:
        for o in orders:
            od = dict(o)
            oid = od['id']
            st = od.get('status') or 'pending'
            st_icon = {
                'pending': '⏳',
                'preparing': '🍳',
                'delivering': '🛵',
                'completed': '✅',
                'cancelled': '❌',
            }.get(st, '⏳')
            dlv_icon = "🍽" if od.get('delivery_type') == 'eat_in' else "🛵"
            name = od.get('full_name') or "Mijoz"
            amt = od.get('total_amount') or 0
            btn_label = f"{st_icon} #{oid} | {dlv_icon} {name[:14]} | {amt:,} so'm"
            markup.row(InlineKeyboardButton(btn_label, callback_data=f"adm_order_{oid}"))

    # Filter tugmalari
    markup.row(
        InlineKeyboardButton(f"🔥 Faol ({active_total})", callback_data="adm_ordfilter_active"),
        InlineKeyboardButton(f"⏳ Kutilmoqda ({pending_cnt})", callback_data="adm_ordfilter_pending"),
    )
    markup.row(
        InlineKeyboardButton(f"🍳 Oshxonada ({prep_cnt})", callback_data="adm_ordfilter_preparing"),
        InlineKeyboardButton(f"🛵 Yo'lda ({deliv_cnt})", callback_data="adm_ordfilter_delivering"),
    )
    markup.row(
        InlineKeyboardButton(f"✅ Tugallangan ({comp_cnt})", callback_data="adm_ordfilter_completed"),
        InlineKeyboardButton(f"❌ Bekor ({canc_cnt})", callback_data="adm_ordfilter_cancelled"),
    )
    markup.row(
        InlineKeyboardButton("📦 Barchasini ko'rish", callback_data="adm_ordfilter_all"),
    )

    if not orders:
        text = (
            f"<b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📭 <i>Ushbu bo'limda hozircha buyurtmalar yo'q.</i>\n\n"
            f"👇 Boshqa holatdagi buyurtmalarni ko'rish uchun filtrni tanlang:"
        )
    else:
        sum_listed = sum((dict(x).get('total_amount') or 0) for x in orders)
        text = (
            f"<b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Ro'yxatda: <b>{len(orders)} ta</b> | 💰 Jami: <b>{sum_listed:,} so'm</b>\n"
            f"⏳ Kutilmoqda: <b>{pending_cnt}</b> | 🍳 Oshxonada: <b>{prep_cnt}</b> | 🛵 Yo'lda: <b>{deliv_cnt}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>Batafsil ko'rish va holatini o'zgartirish uchun buyurtma ustiga bosing:</i>"
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
        await _show_orders_list(call.message, status_filter=None)
    else:
        await _show_orders_list(call.message, status_filter=status)
    await call.answer()


async def admin_order_detail(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    order_id = int(call.data.split("_")[2])
    order_row = await get_order_by_id(order_id)
    if not order_row:
        await call.answer("Buyurtma topilmadi.", show_alert=True)
        return

    order = dict(order_row)
    items = await get_order_items_detail(order_id)
    status = order.get('status') or 'pending'
    created = order.get('created_at')
    date_str = created.strftime('%Y-%m-%d %H:%M') if hasattr(created, 'strftime') else str(created)[:16]

    items_text = ""
    items_subtotal = 0
    lang = await get_user_language(call.from_user.id)
    for it in items:
        it_d = dict(it)
        qty = it_d.get('quantity', 1)
        price = it_d.get('price_at_time') or it_d.get('price') or 0
        items_subtotal += price * qty
        items_text += f"  ▫️ {get_product_name(it_d, lang)} × {qty} = <b>{price * qty:,} so'm</b>\n"

    note = order.get('note')
    note_text = f"\n📝 <b>Izoh:</b> <i>{note}</i>" if note else ""

    promo_code = order.get('promo_code')
    discount_amt = order.get('discount_amount') or 0
    promo_text = ""
    if discount_amt > 0:
        promo_text = (
            f"\n💵 <b>Mahsulotlar narxi:</b> {items_subtotal:,} so'm"
            f"\n🎟 <b>Promokod ({promo_code or 'PROMO'}):</b> -{discount_amt:,} so'm"
        )

    username_display = f"(@{order['username']})" if order.get('username') else ""
    phone_display = order.get('phone_number') or '—'
    from utils.helpers import resolve_human_address
    addr_display = await resolve_human_address(
        order.get('delivery_address'),
        order.get('latitude'),
        order.get('longitude'),
    ) if order.get('delivery_type') != 'eat_in' else (order.get('delivery_address') or '—')
    dlv_label = "🍽 Shu yerda" if order.get('delivery_type') == 'eat_in' else "🛵 Yetkazib berish"
    pay_method = order.get('payment_method') or "Naqd"

    text = (
        f"📋 <b>BUYURTMA TAFSILOTI #{order['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚦 <b>Holat:</b> {STATUS_LABELS.get(status, status)}\n"
        f"📅 <b>Sana:</b> {date_str}\n"
        f"👤 <b>Mijoz:</b> {order.get('full_name') or '—'} {username_display}\n"
        f"📞 <b>Telefon:</b> {phone_display}\n"
        f"🚀 <b>Turi:</b> {dlv_label}\n"
        f"📍 <b>Manzil:</b> {addr_display}\n"
        f"💳 <b>To'lov:</b> {pay_method}"
        f"{note_text}\n\n"
        f"🍛 <b>Buyurtma tarkibi:</b>\n{items_text}"
        f"{promo_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>JAMI SUMMA: {order.get('total_amount', 0):,} so'm</b>"
    )

    markup = get_order_status_keyboard(order_id, status, lang)
    if order.get('latitude') and order.get('longitude'):
        markup.add(InlineKeyboardButton("📍 Xaritada ko'rish (Lokatsiya)", callback_data=f"adm_ordloc_{order_id}"))

    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await call.answer()


async def admin_order_location_cb(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    order_id = int(call.data.split("_")[2])
    order_row = await get_order_by_id(order_id)
    if not order_row:
        await call.answer("Buyurtma topilmadi", show_alert=True)
        return
    order = dict(order_row)
    lat = order.get("latitude")
    lon = order.get("longitude")
    if not lat or not lon:
        await call.answer("Bu buyurtmada GPS lokatsiya mavjud emas", show_alert=True)
        return
    await call.message.answer_location(latitude=float(lat), longitude=float(lon))
    await call.answer("📍 Lokatsiya yuborildi!")


async def admin_change_order_status(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    parts = call.data.split("_")
    order_id = int(parts[2])
    new_status = parts[3]

    prev_row = await get_order_by_id(order_id)
    prev_status = dict(prev_row).get("status") if prev_row else "pending"

    await update_order_status(order_id, new_status)
    await call.answer(f"✅ Holat o'zgartirildi: {STATUS_LABELS.get(new_status, new_status)}", show_alert=True)

    order_row = await get_order_by_id(order_id)
    if order_row:
        order = dict(order_row)
        user_id = order['user_id']
        user_lang = await get_user_language(user_id)

        # Agar kutilayotgan buyurtma 'preparing' qilinsa, yetkazish kanaliga ham yuboramiz
        if prev_status == "pending" and new_status == "preparing":
            from utils.helpers import send_accepted_order_to_delivery_channel
            asyncio.create_task(send_accepted_order_to_delivery_channel(call.bot, order_id))

        from handlers.order_tracking import send_order_status_update
        asyncio.create_task(send_order_status_update(
            bot=call.bot,
            user_id=user_id,
            order_id=order_id,
            new_status=new_status,
            lang=user_lang,
            delivery_type=order.get('delivery_type', 'delivery'),
            courier_phone=COURIER_PHONE if new_status == "delivering" else None,
        ))

        if new_status == "completed":
            from handlers.feedback import send_feedback_request

            async def _send_fb_delayed():
                await asyncio.sleep(3)
                await send_feedback_request(call.bot, user_id, order_id, user_lang)

            asyncio.create_task(_send_fb_delayed())

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


# ══════════════════════════════════════════════════════════════════════
# 4. ➕ MAHSULOT QO'SHISH — KREATIV 5-BOSQICHLI TAOM KONSTRUKTORI
# ══════════════════════════════════════════════════════════════════════

async def admin_start_add_product(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    categories = await get_categories()
    if not categories:
        await message.answer("⚠️ Kategoriyalar yo'q.")
        return
    markup = InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        cd = dict(cat)
        markup.insert(InlineKeyboardButton(
            f"{cd.get('emoji') or '🍽'} {cd['name']}",
            callback_data=f"adm_addprod_cat_{cd['id']}"
        ))
    markup.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_addprod_cancel"))
    await AddProductStates.waiting_category.set()
    await message.answer(
        "➕ <b>YANGI TAOM KONSTRUKTORI</b>\n"
        "<code>[██░░░░░░░░] 1/5 qadam</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📂 <b>1-qadam:</b> Taom qaysi kategoriyaga qo'shilsin?",
        reply_markup=markup,
        parse_mode="HTML"
    )


async def admin_addprod_category(call: types.CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split("_")[3])
    await state.update_data(category_id=cat_id)
    await AddProductStates.waiting_name.set()
    await call.message.edit_text(
        "➕ <b>YANGI TAOM KONSTRUKTORI</b>\n"
        "<code>[████░░░░░░] 2/5 qadam</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✍️ <b>2-qadam:</b> Mahsulotning <b>nomini</b> yozing (masalan: <i>Double Darxan Burger</i>):\n\n"
        "<i>Bekor qilish uchun: /bekor</i>",
        parse_mode="HTML"
    )
    await call.answer()


async def admin_addprod_name(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Nom kamida 2 ta harfdan iborat bo'lishi kerak. Qaytadan yozing:")
        return
    await state.update_data(name=name)
    await AddProductStates.waiting_price.set()
    await message.answer(
        f"➕ <b>YANGI TAOM KONSTRUKTORI</b>\n"
        f"<code>[██████░░░░] 3/5 qadam</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Taom nomi: <b>{name}</b>\n\n"
        f"💰 <b>3-qadam:</b> Taom <b>narxini</b> yozing (so'mda, masalan: <code>38000</code>):",
        parse_mode="HTML"
    )


async def admin_addprod_price(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_admin_keyboard())
        return
    try:
        price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Iltimos, musbat son kiriting (masalan: 35000):")
        return
    await state.update_data(price=price)
    await AddProductStates.waiting_description.set()
    await message.answer(
        f"➕ <b>YANGI TAOM KONSTRUKTORI</b>\n"
        f"<code>[████████░░] 4/5 qadam</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Narxi: <b>{price:,} so'm</b>\n\n"
        f"📝 <b>4-qadam:</b> Taom tarkibi va ishtahani ochuvchi <b>tavsif</b> yozing\n"
        f"<i>(O'tkazib yuborish uchun <code>-</code> yuboring):</i>",
        parse_mode="HTML"
    )


async def admin_addprod_description(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang), reply_markup=get_admin_keyboard(lang))
        return
    desc = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=desc)
    await AddProductStates.waiting_name_ru.set()

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⏭ Tarjimalarni o'tkazib rasmga o'tish", callback_data="adm_addprod_skiptrans"))

    await message.answer(
        get_text("ask_name_ru", lang) + "\n\n👇 <i>Yoki tarjima bosqichlarini 1 bosishda o'tkazib yuboring:</i>",
        reply_markup=markup,
        parse_mode="HTML"
    )


async def admin_addprod_skip_trans_cb(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    await AddProductStates.waiting_image.set()
    await call.message.edit_text(
        "➕ <b>YANGI TAOM KONSTRUKTORI</b>\n"
        "<code>[██████████] 5/5 qadam</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🖼 <b>5-qadam:</b> Taom <b>rasmini</b> yuboring (Telegram rasm yoki URL manzil, rasmsiz saqlash uchun <code>-</code> yozing):",
        parse_mode="HTML"
    )
    await call.answer("Tarjimalar o'tkazib yuborildi")


async def admin_addprod_name_ru(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang), reply_markup=get_admin_keyboard(lang))
        return
    val = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(name_ru=val)
    await AddProductStates.waiting_name_en.set()
    await message.answer(get_text("ask_name_en", lang), parse_mode="HTML")


async def admin_addprod_name_en(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang), reply_markup=get_admin_keyboard(lang))
        return
    val = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(name_en=val)
    await AddProductStates.waiting_desc_ru.set()
    await message.answer(get_text("ask_desc_ru", lang), parse_mode="HTML")


async def admin_addprod_desc_ru(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang), reply_markup=get_admin_keyboard(lang))
        return
    val = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(desc_ru=val)
    await AddProductStates.waiting_desc_en.set()
    await message.answer(get_text("ask_desc_en", lang), parse_mode="HTML")


async def admin_addprod_desc_en(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang), reply_markup=get_admin_keyboard(lang))
        return
    val = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(desc_en=val)
    await AddProductStates.waiting_image.set()
    await message.answer("🖼 <b>Rasm</b> yuboring yoki URL yozing (tire = rasmsiz):", parse_mode="HTML")


async def admin_addprod_image(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text and message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang), reply_markup=get_admin_keyboard(lang))
        return
    image_url = None
    if message.photo:
        image_url = message.photo[-1].file_id
    elif message.text and message.text.strip() != "-":
        image_url = message.text.strip()
    data = await state.get_data()
    pid = await add_product(
        data["category_id"], data["name"], data["price"],
        data.get("description", ""), image_url,
        name_ru=data.get("name_ru"),
        name_en=data.get("name_en"),
        description_ru=data.get("desc_ru"),
        description_en=data.get("desc_en"),
    )
    await state.finish()

    quick_kb = InlineKeyboardMarkup(row_width=2)
    quick_kb.add(
        InlineKeyboardButton("🏷 Chegirma qo'yish", callback_data=f"admin_discount_{pid}"),
        InlineKeyboardButton("🖼 Rasmni yangilash", callback_data=f"admin_image_{pid}"),
    )

    await message.answer(
        f"🎉 <b>YANGI TAOM MENYUGA QO'SHILDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <b>#{pid}</b>\n"
        f"🍔 Nomi: <b>{data['name']}</b>\n"
        f"💰 Narxi: <b>{data['price']:,} so'm</b>\n"
        f"📝 Tavsif: <i>{data.get('description') or '—'}</i>\n"
        f"🖼 Rasm: {'✅ Yuklandi' if image_url else '—'}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(lang)
    )
    await message.answer("👇 <i>Qo'shimcha tezkor sozlamalar:</i>", reply_markup=quick_kb, parse_mode="HTML")
    logging.info(f"Admin {message.from_user.id} mahsulot qo'shdi #{pid}")


async def admin_addprod_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text("❌ Mahsulot qo'shish bekor qilindi.")
    await call.answer()


# ── Admin menyu: rasm almashish / chegirma / yashirish / tarjima ─────

async def admin_image_start(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split("_")[2])
    lang = await get_user_language(call.from_user.id)
    await state.update_data(admin_image_product_id=pid)
    await AdminProductStates.waiting_new_image.set()
    await call.message.answer(get_text("admin_image_ask", lang), parse_mode="HTML")
    await call.answer()


async def admin_image_receive(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text and message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang))
        return
    image_url = None
    if message.photo:
        image_url = message.photo[-1].file_id
    elif message.text:
        image_url = message.text.strip()
    if not image_url:
        await message.answer(get_text("admin_image_invalid", lang))
        return
    data = await state.get_data()
    pid = data["admin_image_product_id"]
    await update_product_image(pid, image_url)
    await state.finish()
    await message.answer(get_text("admin_image_updated", lang), parse_mode="HTML")


async def admin_discount_start(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split("_")[2])
    product = await get_product(pid)
    lang = await get_user_language(call.from_user.id)
    if not product:
        await call.answer(get_text("discount_not_found", lang), show_alert=True)
        return
    prod_d = dict(product)
    old_price = prod_d.get('old_price')
    if old_price and old_price > prod_d['price']:
        await remove_product_discount(pid)
        await call.answer(get_text("discount_removed", lang), show_alert=True)
        return
    await state.update_data(admin_discount_product_id=pid)
    await AdminProductStates.waiting_discount_price.set()
    await call.message.answer(
        get_text("discount_ask_price", lang, name=prod_d['name'], price=prod_d['price']),
        parse_mode="HTML"
    )
    await call.answer()


async def admin_discount_receive(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang))
        return
    try:
        new_price = int(message.text.strip().replace(" ", "").replace(",", ""))
        if new_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer(get_text("discount_invalid_price", lang))
        return
    data = await state.get_data()
    pid = data["admin_discount_product_id"]
    await set_product_discount(pid, new_price)
    await state.finish()
    await message.answer(get_text("discount_set", lang, price=new_price), parse_mode="HTML")


async def admin_toggle_product(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split("_")[2])
    lang = await get_user_language(call.from_user.id)
    new_status = await toggle_product_active(pid)
    if new_status is not None:
        key = "toggle_shown" if new_status else "toggle_hidden"
        await call.answer(get_text(key, lang), show_alert=True)
    else:
        await call.answer(get_text("toggle_error", lang), show_alert=True)


async def admin_translate_start(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split("_")[2])
    product = await get_product(pid)
    lang = await get_user_language(call.from_user.id)
    if not product:
        await call.answer(get_text("product_not_found", lang), show_alert=True)
        return
    await state.update_data(admin_trans_product_id=pid)
    await AdminProductStates.waiting_trans_name_ru.set()
    await call.message.answer(
        get_text("trans_start", lang, name=product['name']) + "\n\n"
        + get_text("ask_name_ru", lang),
        parse_mode="HTML"
    )
    await call.answer()


async def admin_trans_name_ru(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang))
        return
    val = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(trans_name_ru=val)
    await AdminProductStates.waiting_trans_name_en.set()
    await message.answer(get_text("ask_name_en", lang), parse_mode="HTML")


async def admin_trans_name_en(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang))
        return
    val = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(trans_name_en=val)
    await AdminProductStates.waiting_trans_desc_ru.set()
    await message.answer(get_text("ask_desc_ru", lang), parse_mode="HTML")


async def admin_trans_desc_ru(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang))
        return
    val = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(trans_desc_ru=val)
    await AdminProductStates.waiting_trans_desc_en.set()
    await message.answer(get_text("ask_desc_en", lang), parse_mode="HTML")


async def admin_trans_desc_en(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("admin_cancelled", lang))
        return
    val = None if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    pid = data["admin_trans_product_id"]
    name_ru = data.get("trans_name_ru")
    name_en = data.get("trans_name_en")
    desc_ru = data.get("trans_desc_ru")
    desc_en = val

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE products
                   SET name_ru = COALESCE($1, name_ru),
                       name_en = COALESCE($2, name_en),
                       description_ru = COALESCE($3, description_ru),
                       description_en = COALESCE($4, description_en)
                   WHERE id = $5""",
                name_ru, name_en, desc_ru, desc_en, pid
            )
        clear_cache()
        await state.finish()
        await message.answer(
            get_text("trans_saved", lang,
                     name_ru=name_ru or "—",
                     name_en=name_en or "—"),
            parse_mode="HTML"
        )
    except Exception as e:
        await state.finish()
        logging.error(f"Tarjima saqlash xatosi: {e}")
        await message.answer(get_text("trans_error", lang))


# ══════════════════════════════════════════════════════════════════════
# 5. 🎟 PROMO KODLAR — KREATIV AKSIYALAR VA KUPONLAR MARKAZI
# ══════════════════════════════════════════════════════════════════════

async def _build_promo_list_view():
    codes = await get_all_promo_codes()
    markup = InlineKeyboardMarkup(row_width=2)

    if not codes:
        text = (
            "🎟 <b>DARXAN BURGER — PROMOKODLAR VA AKSIYALAR MARKAZI</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📭 <i>Hozircha promokodlar yaratilmagan.</i>\n\n"
            "💡 Mijozlarni jalb qilish uchun yangi promokod yarating yoki 1 bosishda VIP kupon generatsiya qiling!"
        )
        markup.add(
            InlineKeyboardButton("➕ Yangi kod yaratish", callback_data="promo_create"),
            InlineKeyboardButton("🎲 Avto VIP-Promo (20%)", callback_data="promo_random"),
        )
        return text, markup

    text = (
        "🎟 <b>DARXAN BURGER — PROMOKODLAR VA AKSIYALAR MARKAZI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    for c in codes:
        cd = dict(c)
        code_str = cd['code']
        pct = cd['discount_percent']
        used = cd.get('used_count') or 0
        max_u = cd.get('max_uses') or 0
        is_act = bool(cd.get('is_active', True))

        if not is_act:
            status_badge = "⏸ To'xtatilgan"
        elif max_u > 0 and used >= max_u:
            status_badge = "🏁 Limit to'lgan"
        else:
            status_badge = "🟢 Faol"

        uses_str = f"{used}/{max_u}" if max_u > 0 else f"{used}/∞"
        text += (
            f"🎫 Kod: <code>{code_str}</code> — <b>-{pct}%</b>\n"
            f"   📊 Holat: {status_badge} | 🔢 Ishlatildi: <b>{uses_str}</b>\n\n"
        )
        toggle_lbl = f"⏸ {code_str}" if is_act else f"▶️ {code_str}"
        markup.row(
            InlineKeyboardButton(toggle_lbl, callback_data=f"promo_toggle_{code_str}"),
            InlineKeyboardButton(f"📢 E'lon qilish", callback_data=f"promo_ann_{code_str}"),
            InlineKeyboardButton(f"🗑 O'chirish", callback_data=f"promo_del_{code_str}"),
        )

    markup.row(
        InlineKeyboardButton("➕ Yangi kod yaratish", callback_data="promo_create"),
        InlineKeyboardButton("🎲 Avto VIP-Promo", callback_data="promo_random"),
    )
    return text, markup


async def admin_promo_list(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    text, markup = await _build_promo_list_view()
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


async def admin_promo_random_cb(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    prefixes = ["DARXAN", "BURGER", "VIP", "COMBO", "HOT"]
    pct = random.choice([15, 20, 25])
    code = f"{random.choice(prefixes)}{pct}"
    await create_promo_code(code, pct, max_uses=50)
    await call.answer(f"🎉 {code} (-{pct}%) promokodi yaratildi!", show_alert=True)
    text, markup = await _build_promo_list_view()
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=markup, parse_mode="HTML")


async def admin_promo_toggle_cb(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    code = call.data.split("_", 2)[2]
    new_state = await toggle_promo_code(code)
    status_txt = "🟢 Yoqildi" if new_state else "⏸ Vaqtincha to'xtatildi"
    await call.answer(f"{code}: {status_txt}")
    text, markup = await _build_promo_list_view()
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass


async def admin_promo_announce_cb(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    code = call.data.split("_", 2)[2]
    from database.crud import get_db_pool
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        promo = await conn.fetchrow("SELECT * FROM promo_codes WHERE code = $1", code.upper())
        users = await conn.fetch("SELECT user_id FROM users")

    if not promo:
        await call.answer("Promokod topilmadi!", show_alert=True)
        return

    pd = dict(promo)
    pct = pd['discount_percent']
    max_u = pd.get('max_uses') or 0
    limit_str = f"Faqat dastlabki <b>{max_u} ta</b> buyurtma uchun!" if max_u > 0 else "Barcha mijozlarimiz uchun amal qiladi!"

    promo_ad = (
        f"🔥 <b>DARXAN BURGERDAN MAXSUS AKSIYA!</b> 🍔\n\n"
        f"Sevimli burgerlaringizga <b>{pct}% CHEGIRMA</b> e'lon qilamiz! 🎉\n\n"
        f"🎟 Maxsus promokod: <code>{code}</code>\n"
        f"⏳ {limit_str}\n\n"
        f"🏃‍♂️ Hoziroq buyurtma bering va promokodni kiriting!"
    )

    sent = 0
    for u in users:
        try:
            await call.bot.send_message(u['user_id'], promo_ad, parse_mode="HTML")
            sent += 1
        except Exception:
            pass

    await call.answer(f"📢 Aksiya {sent} ta mijozga yuborildi!", show_alert=True)


async def admin_promo_create_start(call: types.CallbackQuery, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    await PromoCodeStates.waiting_code.set()
    await call.message.answer(
        "🎟 <b>YANGI PROMOKOD YARATISH (1/3)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Promokod nomini yozing (masalan: <code>DARXAN25</code> yoki <code>BAHOR20</code>):\n\n"
        "<i>Bekor qilish uchun: /bekor</i>",
        parse_mode="HTML"
    )
    await call.answer()


async def admin_promo_code_name(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.")
        return
    code = message.text.strip().upper()
    if len(code) < 3:
        await message.answer("⚠️ Kod kamida 3 ta belgidan iborat bo'lishi kerak:")
        return
    await state.update_data(promo_code=code)
    await PromoCodeStates.waiting_discount.set()
    await message.answer(
        f"🎟 <b>YANGI PROMOKOD YARATISH (2/3)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Kod: <code>{code}</code>\n\n"
        f"💰 <b>Chegirma foizini yozing (1 dan 100 gacha, masalan: 20):</b>",
        parse_mode="HTML"
    )


async def admin_promo_discount(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Bekor qilindi.")
        return
    try:
        pct = int(message.text.strip().replace("%", ""))
        if pct < 1 or pct > 100:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ 1 dan 100 gacha son yozing:")
        return
    await state.update_data(discount_percent=pct)
    await PromoCodeStates.waiting_max_uses.set()
    await message.answer(
        f"🎟 <b>YANGI PROMOKOD YARATISH (3/3)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Chegirma: <b>{pct}%</b>\n\n"
        f"🔢 <b>Necha marta ishlatilishi mumkin?</b>\n"
        f"<i>(Cheksiz qilish uchun <code>0</code> yozing):</i>",
        parse_mode="HTML"
    )


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
        await message.answer("⚠️ 0 yoki musbat son yozing:")
        return
    data = await state.get_data()
    await create_promo_code(data['promo_code'], data['discount_percent'], max_uses)
    await state.finish()
    uses_text = f"{max_uses} marta" if max_uses > 0 else "♾ Cheksiz"
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📢 Mijozlarga e'lon qilish", callback_data=f"promo_ann_{data['promo_code']}"),
    )
    await message.answer(
        f"🎉 <b>YANGI PROMOKOD MUVAFFAQIYATLI YARATILDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎟 Kod: <code>{data['promo_code']}</code>\n"
        f"💰 Chegirma: <b>{data['discount_percent']}%</b>\n"
        f"🔢 Foydalanish limiti: <b>{uses_text}</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )


async def admin_promo_delete(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    code = call.data.split("_", 2)[2]
    await delete_promo_code(code)
    await call.answer(f"🗑 {code} o'chirildi!", show_alert=True)
    text, markup = await _build_promo_list_view()
    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
# 6. 📥 HISOBOT (CSV) — KREATIV BUXGALTERIYA VA EKSPORT MARKAZI
# ══════════════════════════════════════════════════════════════════════

async def _send_csv_report(target_message: types.Message, period: str = "all"):
    orders = await get_orders_for_export()
    now_date = date.today()

    filtered = []
    for o in orders:
        od = dict(o)
        created_str = str(od.get('created_at') or '')[:10]
        if period == "today" and created_str != now_date.isoformat():
            continue
        if period == "week" and created_str < (now_date - timedelta(days=7)).isoformat():
            continue
        filtered.append(od)

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📅 Bugungi (CSV)", callback_data="csv_exp_today"),
        InlineKeyboardButton("📆 Haftalik (CSV)", callback_data="csv_exp_week"),
    )
    markup.add(
        InlineKeyboardButton("🗓 Barcha buyurtmalar (CSV)", callback_data="csv_exp_all"),
        InlineKeyboardButton("👥 Mijozlar bazasi (CSV)", callback_data="csv_exp_users"),
    )

    if not filtered:
        await target_message.answer(
            "📥 <b>Tanlangan davr uchun buyurtmalar topilmadi.</b>\n"
            "Boshqa davrni tanlang:",
            reply_markup=markup,
            parse_mode="HTML"
        )
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Mijoz", "Telefon", "Turi", "To'lov usuli",
        "Promokod", "Chegirma (so'm)", "Jami summa (so'm)",
        "Manzil", "Izoh", "Holat", "Sana"
    ])

    total_rev = 0
    total_disc = 0
    comp_cnt = 0
    canc_cnt = 0

    for od in filtered:
        created = od.get('created_at')
        date_str = created.strftime('%Y-%m-%d %H:%M') if hasattr(created, 'strftime') else str(created)[:16]
        d_type = "Shu yerda" if od.get('delivery_type') == 'eat_in' else "Yetkazib berish"
        st = od.get('status') or 'pending'
        amt = od.get('total_amount') or 0
        disc = od.get('discount_amount') or 0

        if st != 'cancelled':
            total_rev += amt
            total_disc += disc
        if st == 'completed':
            comp_cnt += 1
        elif st == 'cancelled':
            canc_cnt += 1

        writer.writerow([
            od.get('id'),
            od.get('full_name') or '—',
            od.get('order_phone') or od.get('user_phone') or '—',
            d_type,
            od.get('payment_method') or 'Naqd',
            od.get('promo_code') or '—',
            disc,
            amt,
            od.get('delivery_address') or '—',
            od.get('note') or '—',
            STATUS_LABELS.get(st, st),
            date_str,
        ])

    csv_bytes = output.getvalue().encode('utf-8-sig')
    doc = io.BytesIO(csv_bytes)
    doc.name = f"darxan_buyurtmalar_{period}_{now_date.isoformat()}.csv"

    period_names = {
        "today": "Bugungi kun",
        "week": "Oxirgi 7 kun",
        "all": "Barcha davr",
    }

    caption = (
        f"📥 <b>DARXAN BURGER — BUXGALTERIYA HISOBOTI (CSV)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗓 Davr: <b>{period_names.get(period, 'Barchasi')}</b>\n"
        f"📦 Jami buyurtmalar: <b>{len(filtered)} ta</b>\n"
        f"✅ Tugallangan: <b>{comp_cnt} ta</b> | ❌ Bekor: <b>{canc_cnt} ta</b>\n"
        f"🎟 Berilgan chegirmalar: <b>{total_disc:,} so'm</b>\n"
        f"💰 Sof tushum: <b>{total_rev:,} so'm</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Faylni Excel yoki Google Sheets dasturida ochishingiz mumkin.</i>"
    )
    await target_message.answer_document(doc, caption=caption, reply_markup=markup, parse_mode="HTML")


async def admin_csv_export(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    await _send_csv_report(message, period="all")


async def admin_csv_export_cb(call: types.CallbackQuery):
    if not _is_admin(call.from_user.id):
        return
    kind = call.data.split("_")[2]
    if kind == "users":
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            users = await conn.fetch("SELECT * FROM users ORDER BY created_at DESC")
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["User ID", "Ism", "Username", "Telefon", "Til", "Ro'yxatdan o'tgan sana"])
        for u in users:
            ud = dict(u)
            writer.writerow([
                ud.get("user_id"),
                ud.get("full_name") or "—",
                f"@{ud['username']}" if ud.get("username") else "—",
                ud.get("phone_number") or "—",
                ud.get("language") or "uz",
                str(ud.get("created_at") or "")[:16],
            ])
        doc = io.BytesIO(output.getvalue().encode("utf-8-sig"))
        doc.name = f"darxan_mijozlar_{date.today().isoformat()}.csv"
        await call.message.answer_document(
            doc,
            caption=f"👥 <b>Darxan Burger — Mijozlar bazasi</b>\nJami: <b>{len(users)} nafar</b> mijoz",
            parse_mode="HTML"
        )
        await call.answer("👥 Mijozlar bazasi yuklandi!")
        return

    await _send_csv_report(call.message, period=kind)
    await call.answer("📥 CSV hisobot tayyor!")


# ── Asosiy menuga qaytish ────────────────────────────────────────────

async def admin_back_to_main(message: types.Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.finish()
    from keyboards.main_menu import get_admin_main_menu
    lang = await get_user_language(message.from_user.id)
    await message.answer("🏠 <b>Asosiy menyuga qaytdingiz!</b>", reply_markup=get_admin_main_menu(lang), parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════
# 7. KAFE KANALIDAGI (-1003885234768) QABUL QILISH / BEKOR QILISH
# ══════════════════════════════════════════════════════════════════════

async def cafe_accept_order_callback(call: types.CallbackQuery):
    try:
        order_id = int(call.data.split("_")[2])
    except Exception:
        await call.answer("⚠️ Noto'g'ri buyurtma raqami", show_alert=True)
        return

    order_row = await get_order_by_id(order_id)
    if not order_row:
        await call.answer("⚠️ Buyurtma topilmadi!", show_alert=True)
        return
    order = dict(order_row)

    current_status = order.get("status") or "pending"
    if current_status in ("preparing", "delivering", "completed"):
        await call.answer("ℹ️ Bu buyurtma allaqachon qabul qilingan!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    if current_status == "cancelled":
        await call.answer("ℹ️ Bu buyurtma allaqachon bekor qilingan!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    await update_order_status(order_id, "preparing")
    await call.answer("✅ Buyurtma qabul qilindi!", show_alert=False)

    is_eat_in = (
        order.get("delivery_type") == "eat_in"
        or (order.get("delivery_address") and "stol" in str(order.get("delivery_address", "")).lower())
    )
    from utils.helpers import get_delivery_start_keyboard
    cafe_next_kb = get_delivery_start_keyboard(order_id, is_eat_in=True) if is_eat_in else None

    try:
        orig_html = call.message.html_text or call.message.caption or call.message.text or ""
        updated_html = orig_html.replace(
            "⏳ <i>Holat: Kafe tasdiqlashi kutilmoqda...</i>",
            "✅ <b>Holat: KAFE TOMONIDAN QABUL QILINDI</b>"
        )
        if "✅ <b>Holat:" not in updated_html:
            updated_html += "\n\n✅ <b>Holat: KAFE TOMONIDAN QABUL QILINDI</b>"

        if call.message.caption is not None:
            await call.message.edit_caption(updated_html, parse_mode="HTML", reply_markup=cafe_next_kb)
        else:
            await call.message.edit_text(updated_html, parse_mode="HTML", reply_markup=cafe_next_kb)
    except Exception as e:
        logging.warning(f"Kanal xabarini yangilashda xatolik: {e}")
        try:
            await call.message.edit_reply_markup(reply_markup=cafe_next_kb)
        except Exception:
            pass

    user_id = order["user_id"]
    user_lang = await get_user_language(user_id)
    msg_key = "cafe_order_accepted_eat_in" if is_eat_in else "cafe_order_accepted_delivery"
    customer_msg = get_text(msg_key, user_lang, order_id=order_id)

    try:
        await call.bot.send_message(user_id, customer_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Mijozga qabul qilinganlik xabarini yuborishda xato: {e}")

    from utils.helpers import send_accepted_order_to_delivery_channel
    asyncio.create_task(send_accepted_order_to_delivery_channel(call.bot, order_id))


async def cafe_reject_order_callback(call: types.CallbackQuery):
    try:
        order_id = int(call.data.split("_")[2])
    except Exception:
        await call.answer("⚠️ Noto'g'ri buyurtma raqami", show_alert=True)
        return

    order_row = await get_order_by_id(order_id)
    if not order_row:
        await call.answer("⚠️ Buyurtma topilmadi!", show_alert=True)
        return
    order = dict(order_row)

    current_status = order.get("status") or "pending"
    if current_status == "cancelled":
        await call.answer("ℹ️ Bu buyurtma allaqachon bekor qilingan!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    if current_status in ("preparing", "delivering", "completed"):
        await call.answer("ℹ️ Bu buyurtma allaqachon qabul qilingan!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    await update_order_status(order_id, "cancelled")
    await call.answer("❌ Buyurtma bekor qilindi!", show_alert=False)

    try:
        orig_html = call.message.html_text or call.message.caption or call.message.text or ""
        updated_html = orig_html.replace(
            "⏳ <i>Holat: Kafe tasdiqlashi kutilmoqda...</i>",
            "❌ <b>Holat: BEKOR QILINDI</b>"
        )
        if "❌ <b>Holat:" not in updated_html:
            updated_html += "\n\n❌ <b>Holat: BEKOR QILINDI</b>"

        if call.message.caption is not None:
            await call.message.edit_caption(updated_html, parse_mode="HTML", reply_markup=None)
        else:
            await call.message.edit_text(updated_html, parse_mode="HTML", reply_markup=None)
    except Exception as e:
        logging.warning(f"Kanal xabarini yangilashda xatolik: {e}")
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    user_id = order["user_id"]
    user_lang = await get_user_language(user_id)
    customer_msg = get_text("cafe_order_rejected", user_lang, order_id=order_id)

    try:
        await call.bot.send_message(user_id, customer_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Mijozga bekor qilinganlik xabarini yuborishda xato: {e}")


# ══════════════════════════════════════════════════════════════════════
# 8. YETKAZIB BERISH KANALIDAGI (-1003943860489) 2 BOSQICHLI KURYER TUGMALARI
#    1-bosqich: "🛵 Yo'lga chiqish" (dlv_start_{order_id}) -> 2-tugmaga aylanadi
#    2-bosqich: "✅ Buyurtma yetkazildi" (dlv_finish_{order_id}) -> yakunlanadi
# ══════════════════════════════════════════════════════════════════════

async def delivery_start_callback(call: types.CallbackQuery):
    """
    -1003943860489 kanalda 1-tugma ("🛵 Yo'lga chiqish") bosilganda:
      1. Buyurtma holati 'delivering' ga o'zgaradi
      2. Kanaldagi 1-tugma o'rniga ketma-ketlikda 2-tugma ("✅ Buyurtma yetkazildi") chiqadi
      3. Mijozga kreativ "Kuryer yo'lga chiqdi!" xabari boradi
    """
    try:
        order_id = int(call.data.split("_")[2])
    except Exception:
        await call.answer("⚠️ Noto'g'ri buyurtma raqami", show_alert=True)
        return

    order_row = await get_order_by_id(order_id)
    if not order_row:
        await call.answer("⚠️ Buyurtma topilmadi!", show_alert=True)
        return
    order = dict(order_row)

    current_status = order.get("status") or "preparing"
    if current_status == "completed":
        await call.answer("ℹ️ Bu buyurtma allaqachon yetkazib berilgan!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    if current_status == "cancelled":
        await call.answer("ℹ️ Bu buyurtma bekor qilingan!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    is_eat_in = (
        order.get("delivery_type") == "eat_in"
        or (order.get("delivery_address") and "stol" in str(order.get("delivery_address", "")).lower())
    )

    await update_order_status(order_id, "delivering")
    await call.answer(
        "🍽 Buyurtma «Tayyorlandi» holatiga o'tkazildi!"
        if is_eat_in
        else "🛵 Oq yo'l! Buyurtma «Yo'lda» holatiga o'tkazildi!",
        show_alert=False,
    )

    from utils.helpers import get_delivery_complete_keyboard
    next_kb = get_delivery_complete_keyboard(order_id, is_eat_in=is_eat_in)
    courier_name = call.from_user.full_name if call.from_user else ("Ofitsiant" if is_eat_in else "Kuryer")

    try:
        orig_html = call.message.html_text or call.message.caption or call.message.text or ""
        if is_eat_in:
            status_banner = (
                f"🍽 <b>Holat: BUYURTMA TAYYORLANDI (Stolga yetkazilmoqda...)</b>\n"
                f"👨‍🍳 <b>Mas'ul:</b> {courier_name}"
            )
        else:
            status_banner = (
                f"🛵 <b>Holat: KURYER YO'LGA CHIQDI (Yetkazilmoqda...)</b>\n"
                f"🚴‍♂️ <b>Kuryer:</b> {courier_name}"
            )
        if "✅ <i>Kafe tomonidan qabul qilindi</i>" in orig_html:
            updated_html = orig_html.replace(
                "✅ <i>Kafe tomonidan qabul qilindi</i>",
                status_banner
            )
        elif "✅ <b>Holat: KAFE TOMONIDAN QABUL QILINDI</b>" in orig_html:
            updated_html = orig_html.replace(
                "✅ <b>Holat: KAFE TOMONIDAN QABUL QILINDI</b>",
                status_banner
            )
        else:
            updated_html = orig_html + f"\n\n{status_banner}"

        if call.message.caption is not None:
            await call.message.edit_caption(updated_html, parse_mode="HTML", reply_markup=next_kb)
        else:
            await call.message.edit_text(updated_html, parse_mode="HTML", reply_markup=next_kb)
    except Exception as e:
        logging.warning(f"Yetkazish kanali xabarini yangilashda xato: {e}")
        try:
            await call.message.edit_reply_markup(reply_markup=next_kb)
        except Exception:
            pass

    # Mijozga kreativ xabar yuborish
    user_id = order["user_id"]
    user_lang = await get_user_language(user_id)
    from utils.helpers import resolve_human_address
    address = await resolve_human_address(
        order.get("delivery_address"),
        order.get("latitude"),
        order.get("longitude"),
    ) if not is_eat_in else (order.get("delivery_address") or "Kafeda")
    courier_phone_line = f"\n📞 <b>Kuryer telefoni:</b> {COURIER_PHONE}" if (COURIER_PHONE and not is_eat_in) else ""

    if is_eat_in:
        if user_lang == "ru":
            customer_msg = (
                f"🍽🔥 <b>Отличная новость! Заказ #{order_id} готов!</b>\n\n"
                f"✨ Ваши горячие и ароматные блюда от <b>Darxan Burger</b> готовы и уже подаются к вашему столу!\n\n"
                f"🪑 <b>Стол:</b> {address}\n\n"
                f"😋 <i>Приятного аппетита!</i> 🍔"
            )
        elif user_lang == "en":
            customer_msg = (
                f"🍽🔥 <b>Great news! Order #{order_id} is ready!</b>\n\n"
                f"✨ Your hot and delicious <b>Darxan Burger</b> meal is ready and being served to your table!\n\n"
                f"🪑 <b>Table:</b> {address}\n\n"
                f"😋 <i>Bon appétit!</i> 🍔"
            )
        else:
            customer_msg = (
                f"🍽🔥 <b>Suyunchi! Buyurtma #{order_id} tayyor bo'ldi!</b>\n\n"
                f"✨ Issiqqina va xushbo'y <b>Darxan Burger</b> taomlaringiz tayyorlandi "
                f"va stolingizga olib kelinmoqda! 🚀\n\n"
                f"🪑 <b>Stol:</b> {address}\n\n"
                f"😋 <i>Yoqimli ishtaha tilaymiz!</i> 🍔"
            )
    else:
        if user_lang == "ru":
            customer_msg = (
                f"🛵💨 <b>Отличная новость! Заказ #{order_id} уже в пути!</b>\n\n"
                f"🔥 Ваши горячие и ароматные блюда от <b>Darxan Burger</b> бережно упакованы в термосумку, "
                f"и наш курьер уже мчится к вам! 🚀\n\n"
                f"📍 <b>Адрес доставки:</b> {address}"
                f"{courier_phone_line}\n\n"
                f"⏰ <i>Совсем скоро будем у вашей двери — держите телефон рядом!</i> 😋🍔"
            )
        elif user_lang == "en":
            customer_msg = (
                f"🛵💨 <b>Great news! Order #{order_id} is on the way!</b>\n\n"
                f"🔥 Your hot and delicious <b>Darxan Burger</b> meal is packed in a thermal bag "
                f"and our courier is heading straight to you! 🚀\n\n"
                f"📍 <b>Address:</b> {address}"
                f"{courier_phone_line}\n\n"
                f"⏰ <i>We will be at your door very soon!</i> 😋🍔"
            )
        else:
            customer_msg = (
                f"🛵💨 <b>Suyunchi! Buyurtma #{order_id} yo'lga chiqdi!</b>\n\n"
                f"🔥 Issiqqina va xushbo'y <b>Darxan Burger</b> taomlaringiz maxsus termo-qopga joylandi "
                f"va chaqqon kuryerimiz siz tomonga uchib ketmoqda! 🚀\n\n"
                f"📍 <b>Manzil:</b> {address}"
                f"{courier_phone_line}\n\n"
                f"⏰ <i>Tez orada eshigingiz oldida bo'lamiz, telefoningizni yaqinroq tuting!</i> 😋🍔"
            )

    try:
        await call.bot.send_message(user_id, customer_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Mijozga yo'lga chiqqanlik xabarini yuborishda xato: {e}")


async def delivery_finish_callback(call: types.CallbackQuery):
    """
    -1003943860489 kanalda 2-tugma ("✅ Buyurtma yetkazildi") bosilganda:
      1. Buyurtma holati 'completed' ga o'zgaradi
      2. Kanaldagi xabar "✅ BUYURTMA MUVAFFAQIYATLI YETKAZILDI!" holatiga o'tadi va tugma yopiladi
      3. Mijozga kreativ minnatdorchilik xabari va 5 yulduzli baholash so'rovi boradi
    """
    try:
        order_id = int(call.data.split("_")[2])
    except Exception:
        await call.answer("⚠️ Noto'g'ri buyurtma raqami", show_alert=True)
        return

    order_row = await get_order_by_id(order_id)
    if not order_row:
        await call.answer("⚠️ Buyurtma topilmadi!", show_alert=True)
        return
    order = dict(order_row)

    current_status = order.get("status") or "delivering"
    if current_status == "completed":
        await call.answer("ℹ️ Bu buyurtma allaqachon yakunlangan!", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    await update_order_status(order_id, "completed")
    await call.answer("🎉 Barakalla! Buyurtma muvaffaqiyatli yetkazildi!", show_alert=False)

    courier_name = call.from_user.full_name if call.from_user else "Kuryer"
    time_str, _ = _uz_now_str()

    try:
        orig_html = call.message.html_text or call.message.caption or call.message.text or ""
        done_banner = (
            f"🎉 <b>Holat: BUYURTMA MUVAFFAQIYATLI YETKAZILDI! ✅</b>\n"
            f"🚴‍♂️ <b>Topshirdi:</b> {courier_name} | 🕒 <b>Vaqt:</b> {time_str}"
        )
        if "🛵 <b>Holat: KURYER YO'LGA CHIQDI (Yetkazilmoqda...)</b>" in orig_html:
            updated_html = orig_html.replace(
                "🛵 <b>Holat: KURYER YO'LGA CHIQDI (Yetkazilmoqda...)</b>",
                done_banner
            )
        elif "🍽 <b>Holat: BUYURTMA TAYYORLANDI (Stolga yetkazilmoqda...)</b>" in orig_html:
            updated_html = orig_html.replace(
                "🍽 <b>Holat: BUYURTMA TAYYORLANDI (Stolga yetkazilmoqda...)</b>",
                done_banner
            )
        elif "✅ <i>Kafe tomonidan qabul qilindi</i>" in orig_html:
            updated_html = orig_html.replace(
                "✅ <i>Kafe tomonidan qabul qilindi</i>",
                done_banner
            )
        elif "✅ <b>Holat: KAFE TOMONIDAN QABUL QILINDI</b>" in orig_html:
            updated_html = orig_html.replace(
                "✅ <b>Holat: KAFE TOMONIDAN QABUL QILINDI</b>",
                done_banner
            )
        else:
            updated_html = orig_html + f"\n\n{done_banner}"

        if call.message.caption is not None:
            await call.message.edit_caption(updated_html, parse_mode="HTML", reply_markup=None)
        else:
            await call.message.edit_text(updated_html, parse_mode="HTML", reply_markup=None)
    except Exception as e:
        logging.warning(f"Yetkazish kanali yakuniy xabarini yangilashda xato: {e}")
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    # Mijozga kreativ yakuniy xabar va baholash so'rovi
    user_id = order["user_id"]
    user_lang = await get_user_language(user_id)

    if user_lang == "ru":
        customer_msg = (
            f"🎉🍔 <b>Заказ #{order_id} успешно доставлен!</b>\n\n"
            f"💖 От всей души благодарим вас за выбор <b>Darxan Burger</b>!\n"
            f"😋 Надеемся, наши горячие блюда подарят вам отличное настроение. <b>Приятного аппетита!</b> ✨\n\n"
            f"🔄 <i>Будем рады видеть вас снова!</i> ❤️"
        )
    elif user_lang == "en":
        customer_msg = (
            f"🎉🍔 <b>Order #{order_id} has been delivered!</b>\n\n"
            f"💖 Thank you so much for choosing <b>Darxan Burger</b>!\n"
            f"😋 We hope you enjoy your meal. <b>Bon appétit!</b> ✨\n\n"
            f"🔄 <i>We look forward to serving you again soon!</i> ❤️"
        )
    else:
        customer_msg = (
            f"🎉🍔 <b>Buyurtma #{order_id} muvaffaqiyatli yetkazildi!</b>\n\n"
            f"💖 <b>Darxan Burger</b>ni tanlaganingiz uchun chin qalbimizdan rahmat!\n"
            f"😋 Issiqqina taomlarimiz sizga va yaqinlaringizga manzur bo'ladi degan umiddamiz. "
            f"<b>Yoqimli ishtaha tilaymiz!</b> ✨\n\n"
            f"🔄 <i>Yana shunday mazali lahzalar uchun sizni doim kutib qolamiz!</i> ❤️"
        )

    try:
        await call.bot.send_message(user_id, customer_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Mijozga yetkazilganlik xabarini yuborishda xato: {e}")

    # 3 soniyadan so'ng 5 yulduzli baholash so'rovini yuborish
    try:
        from handlers.feedback import send_feedback_request

        async def _send_fb():
            await asyncio.sleep(3)
            await send_feedback_request(call.bot, user_id, order_id, user_lang)

        asyncio.create_task(_send_fb())
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
# HANDLERLARNI RO'YXATDAN O'TKAZISH
# ══════════════════════════════════════════════════════════════════════

def register_admin_handlers(dp: Dispatcher):
    _STATS_TEXTS   = ["📊 Statistika", "📊 Статистика", "📊 Statistics"]
    _BCAST_TEXTS   = ["📢 Xabar tarqatish", "📢 Рассылка", "📢 Broadcast"]
    _BACK_TEXTS    = ["⬅️ Asosiy menu", "⬅️ Главное меню", "⬅️ Main Menu"]
    _ORDERS_TEXTS  = ["📦 Buyurtmalar", "📦 Заказы", "📦 Orders"]
    _ADDPROD_TEXTS = ["➕ Mahsulot qo'shish", "➕ Добавить продукт", "➕ Add Product"]
    _PROMO_TEXTS   = ["🎟 Promo kodlar", "🎟 Промо-коды", "🎟 Promo Codes"]
    _CSV_TEXTS     = ["📥 Hisobot (CSV)", "📥 Отчёт (CSV)", "📥 Report (CSV)"]

    # Kafe kanalidagi (-1003885234768) Qabul qilish / Bekor qilish inline tugmalari
    dp.register_callback_query_handler(
        cafe_accept_order_callback,
        lambda c: c.data and c.data.startswith("cafe_accept_"),
        state="*",
    )
    dp.register_callback_query_handler(
        cafe_reject_order_callback,
        lambda c: c.data and c.data.startswith("cafe_reject_"),
        state="*",
    )

    # Yetkazib berish kanalidagi (-1003943860489) ketma-ket 2 ta kuryer tugmasi
    dp.register_callback_query_handler(
        delivery_start_callback,
        lambda c: c.data and c.data.startswith("dlv_start_"),
        state="*",
    )
    dp.register_callback_query_handler(
        delivery_finish_callback,
        lambda c: c.data and c.data.startswith("dlv_finish_"),
        state="*",
    )

    # /admin va Dashboard yangilash
    dp.register_message_handler(cmd_admin, commands=['admin'], state="*")
    dp.register_callback_query_handler(admin_dash_refresh_cb, text="adm_dash_refresh", state="*")

    # Statistika va Fikrlar
    dp.register_message_handler(stats_handler, lambda m: m.text in _STATS_TEXTS, state="*")
    dp.register_callback_query_handler(admin_stats_refresh_cb, text="adm_stats_refresh", state="*")
    dp.register_callback_query_handler(admin_stats_feedbacks_cb, text="adm_stats_feedbacks", state="*")

    # Xabar tarqatish (Broadcast)
    dp.register_message_handler(start_broadcast, lambda m: m.text in _BCAST_TEXTS, state="*")
    dp.register_callback_query_handler(cancel_broadcast_cb, text="adm_bcast_cancel", state="*")
    dp.register_message_handler(send_broadcast, state=AdminStates.broadcast_message, content_types=types.ContentTypes.ANY)

    # Asosiy menyuga qaytish
    dp.register_message_handler(admin_back_to_main, lambda m: m.text in _BACK_TEXTS, state="*")

    # Buyurtmalar
    dp.register_message_handler(admin_orders, lambda m: m.text in _ORDERS_TEXTS, state="*")
    dp.register_callback_query_handler(
        admin_order_detail,
        lambda c: c.data and c.data.startswith("adm_order_") and not c.data.startswith("adm_ordstatus_") and not c.data.startswith("adm_ordfilter_"),
        state="*"
    )
    dp.register_callback_query_handler(admin_order_location_cb, lambda c: c.data and c.data.startswith("adm_ordloc_"), state="*")
    dp.register_callback_query_handler(admin_change_order_status, lambda c: c.data and c.data.startswith("adm_ordstatus_"), state="*")
    dp.register_callback_query_handler(admin_order_filter, lambda c: c.data and c.data.startswith("adm_ordfilter_"), state="*")
    dp.register_callback_query_handler(admin_orders_back, text="adm_orders_back", state="*")

    # Mahsulot qo'shish
    dp.register_message_handler(admin_start_add_product, lambda m: m.text in _ADDPROD_TEXTS, state="*")
    dp.register_callback_query_handler(admin_addprod_category, lambda c: c.data and c.data.startswith("adm_addprod_cat_"), state=AddProductStates.waiting_category)
    dp.register_callback_query_handler(admin_addprod_skip_trans_cb, text="adm_addprod_skiptrans", state="*")
    dp.register_callback_query_handler(admin_addprod_cancel, lambda c: c.data == "adm_addprod_cancel", state="*")
    dp.register_message_handler(admin_addprod_name, state=AddProductStates.waiting_name)
    dp.register_message_handler(admin_addprod_price, state=AddProductStates.waiting_price)
    dp.register_message_handler(admin_addprod_description, state=AddProductStates.waiting_description)
    dp.register_message_handler(admin_addprod_name_ru, state=AddProductStates.waiting_name_ru)
    dp.register_message_handler(admin_addprod_name_en, state=AddProductStates.waiting_name_en)
    dp.register_message_handler(admin_addprod_desc_ru, state=AddProductStates.waiting_desc_ru)
    dp.register_message_handler(admin_addprod_desc_en, state=AddProductStates.waiting_desc_en)
    dp.register_message_handler(admin_addprod_image, content_types=[types.ContentType.PHOTO, types.ContentType.TEXT], state=AddProductStates.waiting_image)

    # Rasm almashish, Chegirma, Yashirish, Tarjima
    dp.register_callback_query_handler(admin_image_start, lambda c: c.data and c.data.startswith("admin_image_"), state="*")
    dp.register_message_handler(admin_image_receive, content_types=[types.ContentType.PHOTO, types.ContentType.TEXT], state=AdminProductStates.waiting_new_image)
    dp.register_callback_query_handler(admin_discount_start, lambda c: c.data and c.data.startswith("admin_discount_"), state="*")
    dp.register_message_handler(admin_discount_receive, state=AdminProductStates.waiting_discount_price)
    dp.register_callback_query_handler(admin_toggle_product, lambda c: c.data and c.data.startswith("admin_toggle_"), state="*")
    dp.register_callback_query_handler(admin_translate_start, lambda c: c.data and c.data.startswith("admin_translate_"), state="*")
    dp.register_message_handler(admin_trans_name_ru, state=AdminProductStates.waiting_trans_name_ru)
    dp.register_message_handler(admin_trans_name_en, state=AdminProductStates.waiting_trans_name_en)
    dp.register_message_handler(admin_trans_desc_ru, state=AdminProductStates.waiting_trans_desc_ru)
    dp.register_message_handler(admin_trans_desc_en, state=AdminProductStates.waiting_trans_desc_en)

    # Promo kodlar
    dp.register_message_handler(admin_promo_list, lambda m: m.text in _PROMO_TEXTS, state="*")
    dp.register_callback_query_handler(admin_promo_create_start, text="promo_create", state="*")
    dp.register_callback_query_handler(admin_promo_random_cb, text="promo_random", state="*")
    dp.register_callback_query_handler(admin_promo_toggle_cb, lambda c: c.data and c.data.startswith("promo_toggle_"), state="*")
    dp.register_callback_query_handler(admin_promo_announce_cb, lambda c: c.data and c.data.startswith("promo_ann_"), state="*")
    dp.register_message_handler(admin_promo_code_name, state=PromoCodeStates.waiting_code)
    dp.register_message_handler(admin_promo_discount, state=PromoCodeStates.waiting_discount)
    dp.register_message_handler(admin_promo_max_uses, state=PromoCodeStates.waiting_max_uses)
    dp.register_callback_query_handler(admin_promo_delete, lambda c: c.data and c.data.startswith("promo_del_"), state="*")

    # CSV eksport
    dp.register_message_handler(admin_csv_export, lambda m: m.text in _CSV_TEXTS, state="*")
    dp.register_callback_query_handler(admin_csv_export_cb, lambda c: c.data and c.data.startswith("csv_exp_"), state="*")
