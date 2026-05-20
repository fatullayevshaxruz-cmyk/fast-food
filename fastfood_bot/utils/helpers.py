from config import ADMIN_ID, ADMIN_CHANNEL_ID
from aiogram import types


async def notify_admins_new_order(bot, order_id, total_amount, user, items, phone, address,
                                   location=None, note=None, delivery_type="delivery"):
    """Admin va kanalga yangi buyurtma haqida xabar yuborish (rasmlar bilan)."""

    # ── Buyurtma turi ────────────────────────────────────────────────
    if delivery_type == "eat_in" or (address and "Stol raqami" in str(address)):
        order_type_emoji = "🍽️"
        order_type_label = "Shu yerda"
    else:
        order_type_emoji = "🛵"
        order_type_label = "Yetkazib berish"

    address_label = address or "—"

    # ── Mahsulotlar va rasmlarni yig'ish ─────────────────────────────
    items_text = ""
    items_with_price_text = ""
    photo_urls = []   # Barcha rasm URL / file_id lar

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

        # Rasm bor bo'lsa qo'shish (URL ham, file_id ham)
        if image_url:
            photo_urls.append(str(image_url))

    # Takroriy rasmlarni olib tashlash (bir xil taom bir necha marta bo'lsa)
    seen = set()
    unique_photos = []
    for url in photo_urls:
        if url not in seen:
            seen.add(url)
            unique_photos.append(url)

    note_text     = f"\n📝 <b>Izoh:</b> <i>{note}</i>" if note else ""
    phone_display = phone or "ko'rsatilmagan"

    # ── 1. Admin shaxsiga yuborish (qisqa, rasmsiz) ──────────────────
    admin_message = (
        f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
        f"{order_type_emoji} <b>{order_type_label}</b>\n"
        f"📍 {address_label}\n"
        f"📞 {phone_display}\n\n"
        f"🍛 <b>Buyurtma:</b>\n{items_text}\n"
        f"💰 <b>Jami:</b> {total_amount:,} so'm"
        f"{note_text}"
    )

    for admin_id in ADMIN_ID.split(','):
        try:
            await bot.send_message(admin_id.strip(), admin_message, parse_mode="HTML")
        except Exception:
            pass

    # ── 2. Admin kanaliga yuborish (rasmlar bilan) ────────────────────
    if not ADMIN_CHANNEL_ID:
        return

    username_text = f"(@{user.username})" if user.username else ""
    full_message = (
        f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
        f"👤 <b>Mijoz:</b> {user.full_name} {username_text}\n"
        f"📞 <b>Telefon:</b> {phone_display}\n"
        f"{order_type_emoji} <b>Turi:</b> {order_type_label}\n"
        f"📍 <b>Manzil:</b> {address_label}"
        f"{note_text}\n\n"
        f"🍛 <b>Buyurtma tarkibi:</b>\n{items_with_price_text}\n"
        f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm"
    )

    try:
        await _send_to_channel(bot, ADMIN_CHANNEL_ID, full_message, unique_photos)

        # Lokatsiya — faqat yetkazib berish uchun
        if (delivery_type == "delivery"
                and location
                and location.get('lat')
                and location.get('lon')):
            await bot.send_location(
                ADMIN_CHANNEL_ID,
                latitude=location['lat'],
                longitude=location['lon']
            )

    except Exception:
        # Fallback — hech bo'lmasa matn yuborish
        try:
            await bot.send_message(ADMIN_CHANNEL_ID, full_message, parse_mode="HTML")
        except Exception:
            pass


async def _send_to_channel(bot, channel_id, caption: str, photo_urls: list):
    """
    Kanalga xabar + rasmlarni yuborish:
      - 0 rasm  → oddiy matn xabar
      - 1 rasm  → bitta foto + caption
      - 2-10 rasm → media guruh (birinchisida caption)
    """
    if not photo_urls:
        await bot.send_message(channel_id, caption, parse_mode="HTML")
        return

    if len(photo_urls) == 1:
        # Bitta rasm
        await _safe_send_photo(bot, channel_id, photo_urls[0], caption)
        return

    # Ko'p rasm — media guruh (max 10 ta)
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
        # Media group ishlamasa — faqat birinchi rasmni yuborish
        await _safe_send_photo(bot, channel_id, photos_to_send[0], caption)


async def _safe_send_photo(bot, channel_id, photo_url: str, caption: str):
    """Rasmni xavfsiz yuborish — ishlamasa matn xabar."""
    try:
        await bot.send_photo(
            channel_id,
            photo=photo_url,
            caption=caption,
            parse_mode="HTML"
        )
    except Exception:
        # Rasm yuklanmasa — faqat matn
        await bot.send_message(channel_id, caption, parse_mode="HTML")
