import os
import asyncio
import logging
from config import ADMIN_CHANNEL_ID, DELIVERY_CHANNEL_ID
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger(__name__)

# Kanal xabarlarini yuborishga max vaqt (sekund)
_CHANNEL_TIMEOUT = 10


def get_cafe_approval_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """
    -1003885234768 (Kafe/Admin kanali) uchun
    Buyurtmani qabul qilish yoki bekor qilish tugmalari.
    """
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton(
            "✅ Buyurtmani qabul qilish",
            callback_data=f"cafe_accept_{order_id}"
        ),
        InlineKeyboardButton(
            "❌ Bekor qilish",
            callback_data=f"cafe_reject_{order_id}"
        ),
    )
    return markup


async def notify_admins_new_order(bot, order_id, total_amount, user, items, phone, address,
                                   location=None, note=None, delivery_type="delivery",
                                   payment_method="Naqd (Yetkazib berilganda)"):
    """
    Mijoz buyurtma qilganda:
      1. Faqat ADMIN_CHANNEL_ID (-1003885234768) kanaliga yuboriladi
         (✅ Buyurtmani qabul qilish / ❌ Bekor qilish tugmalari bilan).
      2. DELIVERY_CHANNEL_ID (-1003943860489) ga bu bosqichda YUBORILMAYDI!
         Faqat -1003885234768 kanalda "Qabul qilish" bosilgandagina yuboriladi.
    """
    is_delivery = (delivery_type == "delivery" and
                   not (address and "Stol raqami" in str(address)))

    if is_delivery:
        order_type_emoji = "🛵"
        order_type_label = "Yetkazib berish"
    else:
        order_type_emoji = "🍽️"
        order_type_label = "Shu yerda"

    address_label = address or "—"

    # ── Mahsulotlar va rasmlarni yig'ish ─────────────────────────────
    items_with_price_text = ""
    photo_urls            = []

    for i in items:
        try:
            item_d    = dict(i)
            qty       = item_d.get('quantity', 1)
            price     = item_d.get('price', 0)
            name      = item_d.get('name', 'Mahsulot')
            image_url = item_d.get('image_url')
        except Exception:
            qty, price, name, image_url = 1, 0, "Mahsulot", None

        items_with_price_text += f"  ▫️ {name} x {qty} = {price * qty:,} so'm\n"

        if image_url:
            photo_urls.append(str(image_url))

    # Takroriy rasmlarni olib tashlash
    seen = set()
    unique_photos = []
    for url in photo_urls:
        if url not in seen:
            seen.add(url)
            unique_photos.append(url)

    note_text     = f"\n📝 <b>Izoh:</b> <i>{note}</i>" if note else ""
    phone_display = phone or "ko'rsatilmagan"
    username_text = f"(@{user.username})" if getattr(user, 'username', None) else ""
    full_name     = getattr(user, 'full_name', None) or "Mijoz"

    # ── To'lov usuli belgisi ─────────────────────────────────────────
    is_online = payment_method and "Online" in str(payment_method)
    if is_online:
        payment_emoji = "💳"
        payment_label = "Karta orqali to'landi (Click/Payme)"
    else:
        payment_emoji = "💵"
        payment_label = "Naqd pul (Yetkazib berilganda)"

    # ── 1. KAFE KANALI (-1003885234768): Qabul qilish / Bekor qilish tugmalari bilan ──
    if ADMIN_CHANNEL_ID:
        cafe_channel_msg = (
            f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
            f"⏳ <i>Holat: Kafe tasdiqlashi kutilmoqda...</i>\n\n"
            f"👤 <b>Mijoz:</b> {full_name} {username_text}\n"
            f"📞 <b>Telefon:</b> {phone_display}\n"
            f"{order_type_emoji} <b>Turi:</b> {order_type_label}\n"
            f"📍 <b>Manzil:</b> {address_label}"
            f"{note_text}\n\n"
            f"🍛 <b>Buyurtma tarkibi:</b>\n{items_with_price_text}\n"
            f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm\n"
            f"{payment_emoji} <b>To'lov:</b> {payment_label}"
        )
        approval_kb = get_cafe_approval_keyboard(order_id)
        try:
            await asyncio.wait_for(
                _send_to_channel(
                    bot, ADMIN_CHANNEL_ID,
                    cafe_channel_msg,
                    unique_photos,
                    send_location=False,
                    reply_markup=approval_kb,
                ),
                timeout=_CHANNEL_TIMEOUT
            )
        except Exception as e:
            log.error(f"ADMIN_CHANNEL_ID ga yuborishda xato: {e}")


async def send_accepted_order_to_delivery_channel(bot, order_id: int):
    """
    -1003885234768 kanalda buyurtma QABUL QILINGANDAN KEYIN
    -1003943860489 (DELIVERY_CHANNEL_ID) kanaliga buyurtma ma'lumotlari va lokatsiyani yuboradi.
    """
    if not DELIVERY_CHANNEL_ID:
        return

    try:
        from database.crud import get_order_by_id, get_order_items_detail

        order = await get_order_by_id(order_id)
        if not order:
            log.warning(f"send_accepted_order_to_delivery_channel: buyurtma #{order_id} topilmadi")
            return

        order_d = dict(order)
        items_rows = await get_order_items_detail(order_id)
        items = [dict(r) for r in items_rows] if items_rows else []

        delivery_type  = order_d.get("delivery_type") or "delivery"
        address        = order_d.get("delivery_address") or "—"
        phone_display  = order_d.get("phone_number") or "ko'rsatilmagan"
        note           = order_d.get("note")
        total_amount   = order_d.get("total_amount") or 0
        payment_method = order_d.get("payment_method") or "Naqd (Yetkazib berilganda)"
        full_name      = order_d.get("full_name") or "Mijoz"
        username       = order_d.get("username")
        username_text  = f"(@{username})" if username else ""
        lat            = order_d.get("latitude")
        lon            = order_d.get("longitude")

        is_delivery = (delivery_type == "delivery" and
                       not (address and "Stol raqami" in str(address)))

        if is_delivery:
            header_line = f"🛵 <b>Yetkazib berish #{order_id}</b>"
        else:
            header_line = f"🍽️ <b>Shu yerda #{order_id}</b>"

        items_with_price_text = ""
        photo_urls = []

        for i in items:
            qty       = i.get("quantity", 1)
            price     = i.get("price_at_time") or i.get("price") or 0
            name      = i.get("name") or "Mahsulot"
            image_url = i.get("image_url")
            items_with_price_text += f"  ▫️ {name} x {qty} = {price * qty:,} so'm\n"
            if image_url:
                photo_urls.append(str(image_url))

        seen = set()
        unique_photos = []
        for url in photo_urls:
            if url not in seen:
                seen.add(url)
                unique_photos.append(url)

        note_text = f"\n📝 <b>Izoh:</b> <i>{note}</i>" if note else ""

        is_online = payment_method and "Online" in str(payment_method)
        if is_online:
            payment_emoji = "💳"
            payment_label = "Karta orqali to'landi (Click/Payme)"
        else:
            payment_emoji = "💵"
            payment_label = "Naqd pul (Yetkazib berilganda)"

        delivery_msg = (
            f"{header_line}\n"
            f"✅ <i>Kafe tomonidan qabul qilindi</i>\n\n"
            f"👤 <b>Mijoz:</b> {full_name} {username_text}\n"
            f"📞 <b>Telefon:</b> {phone_display}\n"
            f"📍 <b>Manzil:</b> {address}"
            f"{note_text}\n\n"
            f"🍛 <b>Buyurtma tarkibi:</b>\n{items_with_price_text}\n"
            f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm\n"
            f"{payment_emoji} <b>To'lov:</b> {payment_label}"
        )

        await asyncio.wait_for(
            _send_to_channel(
                bot,
                DELIVERY_CHANNEL_ID,
                delivery_msg,
                unique_photos,
                send_location=bool(is_delivery and lat and lon),
                lat=lat,
                lon=lon,
                reply_markup=None,
            ),
            timeout=_CHANNEL_TIMEOUT
        )
    except Exception as e:
        log.error(f"DELIVERY_CHANNEL_ID ga yuborishda xato: {e}", exc_info=True)


async def _send_to_channel(bot, channel_id, caption: str, photo_urls: list,
                            send_location: bool = False,
                            lat: float = None, lon: float = None,
                            reply_markup=None):
    """
    Kanalga xabar + rasmlarni yuborish:
      - 0 rasm  → oddiy matn (reply_markup bilan)
      - 1 rasm  → send_photo (caption va reply_markup bilan)
      - 2-10 rasm → agar reply_markup bo'lsa: avval rasmlar media_group,
                    keyin asosiy matn + reply_markup;
                    agar reply_markup bo'lmasa: media_group (birinchisida caption).
    Keyin agar send_location=True va koordinatlar bo'lsa lokatsiya yuboriladi.
    """
    if not photo_urls:
        await bot.send_message(channel_id, caption, parse_mode="HTML", reply_markup=reply_markup)
    elif len(photo_urls) == 1:
        await _safe_send_photo(bot, channel_id, photo_urls[0], caption, reply_markup=reply_markup)
    else:
        photos_to_send = photo_urls[:10]
        if reply_markup is not None:
            # MediaGroup da inline tugma ishlamagani uchun:
            # 1) Rasmlar albomini yuboramiz
            media = types.MediaGroup()
            for url in photos_to_send:
                media.attach_photo(url)
            try:
                await bot.send_media_group(channel_id, media=media)
            except Exception:
                pass
            # 2) Asosiy buyurtma ma'lumoti + Inline tugmalarni yuboramiz
            await bot.send_message(channel_id, caption, parse_mode="HTML", reply_markup=reply_markup)
        else:
            media = types.MediaGroup()
            for idx, url in enumerate(photos_to_send):
                if idx == 0:
                    media.attach_photo(url, caption=caption, parse_mode="HTML")
                else:
                    media.attach_photo(url)
            try:
                await bot.send_media_group(channel_id, media=media)
            except Exception:
                await _safe_send_photo(bot, channel_id, photos_to_send[0], caption)

    # Lokatsiya
    if send_location and lat and lon:
        try:
            await bot.send_location(channel_id, latitude=float(lat), longitude=float(lon))
        except Exception:
            pass


async def _safe_send_photo(bot, channel_id, photo_url: str, caption: str, reply_markup=None):
    """Rasmni xavfsiz yuborish — ishlamasa faqat matn."""
    try:
        await bot.send_photo(
            channel_id, photo=photo_url,
            caption=caption, parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception:
        await bot.send_message(channel_id, caption, parse_mode="HTML", reply_markup=reply_markup)
