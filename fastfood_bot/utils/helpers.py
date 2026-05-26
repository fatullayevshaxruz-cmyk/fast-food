import os
import asyncio
from config import ADMIN_CHANNEL_ID
from aiogram import types

# Yetkazib berish uchun alohida kanal
DELIVERY_CHANNEL_ID = os.getenv("DELIVERY_CHANNEL_ID", "-1003943860489")

# Kanal xabarlarini yuborishga max vaqt (sekund)
_CHANNEL_TIMEOUT = 8


async def notify_admins_new_order(bot, order_id, total_amount, user, items, phone, address,
                                   location=None, note=None, delivery_type="delivery",
                                   payment_method="Naqd (Yetkazib berilganda)"):
    """
    Buyurtma haqida kanalga xabar yuborish:
      - ADMIN_CHANNEL_ID  : barcha buyurtmalar (eat_in + delivery), lokatsiyasiz
      - DELIVERY_CHANNEL_ID : faqat delivery, lokatsiya bilan
      - Admin shaxsiga: YUBORILMAYDI
    """

    # ── Buyurtma turi ────────────────────────────────────────────────
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
    items_text           = ""
    items_with_price_text = ""
    photo_urls           = []

    for i in items:
        try:
            qty       = i['quantity']
            price     = i['price']
            name      = i['name']
            image_url = i['image_url']
        except Exception:
            qty, price, name, image_url = 1, 0, "Mahsulot", None

        items_text            += f"▫️ {name} x {qty}\n"
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
    username_text = f"(@{user.username})" if user.username else ""

    # ── To'lov usuli belgisi ─────────────────────────────────────────
    is_online = payment_method and "Online" in str(payment_method)
    if is_online:
        payment_emoji = "💳"
        payment_label = "Karta orqali to'landi (Click/Payme)"
    else:
        payment_emoji = "💵"
        payment_label = "Naqd pul (Yetkazib berilganda)"

    # ── 1. ESKI KANAL: barcha buyurtmalar, lokatsiyasiz ──────────────
    if ADMIN_CHANNEL_ID:
        old_channel_msg = (
            f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
            f"👤 <b>Mijoz:</b> {user.full_name} {username_text}\n"
            f"📞 <b>Telefon:</b> {phone_display}\n"
            f"{order_type_emoji} <b>Turi:</b> {order_type_label}\n"
            f"📍 <b>Manzil:</b> {address_label}"
            f"{note_text}\n\n"
            f"🍛 <b>Buyurtma tarkibi:</b>\n{items_with_price_text}\n"
            f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm\n"
            f"{payment_emoji} <b>To'lov:</b> {payment_label}"
        )
        try:
            await asyncio.wait_for(
                _send_to_channel(
                    bot, ADMIN_CHANNEL_ID,
                    old_channel_msg,
                    unique_photos,
                    send_location=False
                ),
                timeout=_CHANNEL_TIMEOUT
            )
        except Exception:
            pass

    # ── 2. YETKAZIB BERISH KANALI: faqat delivery, lokatsiya bilan ───
    if is_delivery and DELIVERY_CHANNEL_ID:
        delivery_msg = (
            f"🛵 <b>Yetkazib berish #{order_id}</b>\n"
            f"👤 <b>Mijoz:</b> {user.full_name} {username_text}\n"
            f"📞 <b>Telefon:</b> {phone_display}\n"
            f"📍 <b>Manzil:</b> {address_label}"
            f"{note_text}\n\n"
            f"🍛 <b>Buyurtma tarkibi:</b>\n{items_with_price_text}\n"
            f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm\n"
            f"{payment_emoji} <b>To'lov:</b> {payment_label}"
        )
        lat = location.get('lat') if location else None
        lon = location.get('lon') if location else None
        try:
            await asyncio.wait_for(
                _send_to_channel(
                    bot, DELIVERY_CHANNEL_ID,
                    delivery_msg,
                    unique_photos,
                    send_location=True,
                    lat=lat,
                    lon=lon
                ),
                timeout=_CHANNEL_TIMEOUT
            )
        except Exception:
            pass


async def _send_to_channel(bot, channel_id, caption: str, photo_urls: list,
                            send_location: bool = False,
                            lat: float = None, lon: float = None):
    """
    Kanalga xabar + rasmlarni yuborish:
      - 0 rasm  → oddiy matn
      - 1 rasm  → send_photo (caption bilan)
      - 2-10 rasm → send_media_group (birinchisida caption)
    Keyin agar send_location=True va koordinatlar bo'lsa lokatsiya yuboriladi.
    """
    if not photo_urls:
        await bot.send_message(channel_id, caption, parse_mode="HTML")
    elif len(photo_urls) == 1:
        await _safe_send_photo(bot, channel_id, photo_urls[0], caption)
    else:
        photos_to_send = photo_urls[:10]
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
            await bot.send_location(channel_id, latitude=lat, longitude=lon)
        except Exception:
            pass


async def _safe_send_photo(bot, channel_id, photo_url: str, caption: str):
    """Rasmni xavfsiz yuborish — ishlamasa faqat matn."""
    try:
        await bot.send_photo(
            channel_id, photo=photo_url,
            caption=caption, parse_mode="HTML"
        )
    except Exception:
        await bot.send_message(channel_id, caption, parse_mode="HTML")
