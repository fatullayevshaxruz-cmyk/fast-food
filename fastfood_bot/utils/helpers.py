from config import ADMIN_ID, ADMIN_CHANNEL_ID
from aiogram import types


async def notify_admins_new_order(bot, order_id, total_amount, user, items, phone, address,
                                   location=None, note=None, delivery_type="delivery"):
    """Admin va kanalga yangi buyurtma haqida xabar yuborish."""

    # ── Buyurtma turi ────────────────────────────────────────────────
    if delivery_type == "eat_in" or (address and "Stol raqami" in str(address)):
        order_type_emoji = "🍽️"
        order_type_label = "Shu yerda"
        address_label = address or "—"
    else:
        order_type_emoji = "🛵"
        order_type_label = "Yetkazib berish"
        address_label = address or "—"

    # ── Mahsulotlar ──────────────────────────────────────────────────
    items_text = ""
    items_with_price_text = ""
    for i in items:
        qty = i['quantity']
        price = i['price']
        name = i['name']
        items_text += f"▫️ {name} x {qty}\n"
        items_with_price_text += f"  ▫️ {name} x {qty} = {price * qty:,} so'm\n"

    note_text = f"\n📝 <b>Izoh:</b> <i>{note}</i>" if note else ""
    phone_display = phone or "ko'rsatilmagan"

    # ── 1. Admin shaxsiga yuborish (qisqa) ──────────────────────────
    admin_message = (
        f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
        f"{order_type_emoji} <b>{order_type_label}</b>\n"
        f"📍 {address_label}\n"
        f"📞 {phone_display}\n\n"
        f"🍛 <b>Buyurtma:</b>\n{items_text}\n"
        f"💰 <b>Jami:</b> {total_amount:,} so'm"
        f"{note_text}"
    )

    admins = ADMIN_ID.split(',')
    for admin_id in admins:
        try:
            await bot.send_message(admin_id.strip(), admin_message, parse_mode="HTML")
        except Exception:
            pass

    # ── 2. Admin kanaliga yuborish (to'liq) ─────────────────────────
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
        # Rasmlarni yig'ish — faqat fayl ID bo'lsa to'g'ridan-to'g'ri yuborish
        photo_file_ids = []
        for item in items:
            image_url = item.get('image_url') if isinstance(item, dict) else None
            if image_url and not image_url.startswith('http'):
                # Bu Telegram file_id — URL emas
                photo_file_ids.append(image_url)

        if photo_file_ids:
            # Birinchi rasmni caption bilan yuborish
            media = types.MediaGroup()
            for idx, fid in enumerate(photo_file_ids[:10]):  # Max 10 rasm
                if idx == 0:
                    media.attach_photo(fid, caption=full_message, parse_mode="HTML")
                else:
                    media.attach_photo(fid)
            await bot.send_media_group(ADMIN_CHANNEL_ID, media=media)
        else:
            # Rasm yo'q — oddiy xabar
            await bot.send_message(ADMIN_CHANNEL_ID, full_message, parse_mode="HTML")

        # Lokatsiya yuborish (faqat yetkazib berish uchun)
        if delivery_type == "delivery" and location and location.get('lat') and location.get('lon'):
            await bot.send_location(ADMIN_CHANNEL_ID,
                                    latitude=location['lat'],
                                    longitude=location['lon'])

    except Exception as e:
        # Rasmlar ishlamasa — oddiy xabar yuborish
        try:
            await bot.send_message(ADMIN_CHANNEL_ID, full_message, parse_mode="HTML")
            if delivery_type == "delivery" and location and location.get('lat') and location.get('lon'):
                await bot.send_location(ADMIN_CHANNEL_ID,
                                        latitude=location['lat'],
                                        longitude=location['lon'])
        except Exception:
            pass
