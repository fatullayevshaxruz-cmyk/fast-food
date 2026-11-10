import os
import re
import time
import asyncio
import logging
import aiohttp
from config import ADMIN_CHANNEL_ID, DELIVERY_CHANNEL_ID
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

log = logging.getLogger(__name__)

# Kanal xabarlarini yuborishga max vaqt (sekund)
_CHANNEL_TIMEOUT = 10

_PLACE_CACHE = {}
_PLACE_CACHE_TTL = 3600  # 1 soat
_COORD_REGEX = re.compile(r"(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")


def _looks_like_raw_gps(address_str: str) -> bool:
    """Manzil matni 'GPS: 39.7886, 64.3855' yoki faqat koordinatadan iboratligini aniqlaydi."""
    if not address_str:
        return True
    s = str(address_str).strip()
    if not s or s in ("—", "Manzil kiritilmagan", "Noma'lum"):
        return True
    low = s.lower()
    if low.startswith("gps") or "gps:" in low or "koordinat" in low:
        return True
    if _COORD_REGEX.search(s):
        # Agar matnda harflar deyarli bo'lmasa (faqat raqam va vergul)
        letters = re.sub(r"[^a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ]", "", s)
        if len(letters) <= 5:
            return True
    return False


async def resolve_human_address(address: str = None, lat: float = None, lon: float = None) -> str:
    """
    Agar manzil 'GPS: 39.7886, 64.3855' yoki koordinata ko'rinishida bo'lsa,
    uni Nominatim / BigDataCloud orqali haqiqiy joy nomiga (viloyat, shahar, tuman,
    mahalla, ko'cha va uy/mo'ljal nomi) aylantirib qaytaradi.
    Hech qachon 'GPS: 39.7886, 64.3855' ko'rinishidagi kod qaytarmaydi!
    """
    raw_addr = (address or "").strip()

    # Agar lat/lon berilmagan bo'lsa, matn ichidan qidirib ko'ramiz
    if (lat is None or lon is None) and raw_addr:
        m = _COORD_REGEX.search(raw_addr)
        if m:
            try:
                lat = float(m.group(1))
                lon = float(m.group(2))
            except Exception:
                pass

    # Agar manzil allaqachon aniq joy nomi bo'lsa (GPS kod bo'lmasa), o'zini qaytaramiz
    if raw_addr and not _looks_like_raw_gps(raw_addr):
        return raw_addr

    if lat is None or lon is None:
        return raw_addr if (raw_addr and not _looks_like_raw_gps(raw_addr)) else "Manzil xaritada belgilangan"

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return raw_addr or "Manzil xaritada belgilangan"

    cache_key = f"{lat_f:.4f},{lon_f:.4f}"
    now = time.time()
    if cache_key in _PLACE_CACHE:
        cached_name, ts = _PLACE_CACHE[cache_key]
        if now - ts < _PLACE_CACHE_TTL:
            return cached_name

    place_name = None

    # 1-usul: OpenStreetMap Nominatim (aniq ko'cha, mahalla, bino va shahar nomi)
    nominatim_url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?format=json&lat={lat_f}&lon={lon_f}&zoom=18&addressdetails=1&accept-language=uz,ru"
    )
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.get(
                nominatim_url,
                headers={"User-Agent": "DarxanBurgerBot/3.0 (uzbekistan delivery)"},
                timeout=aiohttp.ClientTimeout(total=6),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    addr = data.get("address") or {}
                    parts = []

                    # Shahar / Tuman
                    city = (
                        addr.get("city")
                        or addr.get("town")
                        or addr.get("county")
                        or addr.get("city_district")
                        or addr.get("state")
                        or ""
                    ).strip()
                    if city:
                        parts.append(city)

                    # Tuman / Mahalla / Mavze
                    area = (
                        addr.get("suburb")
                        or addr.get("neighbourhood")
                        or addr.get("quarter")
                        or addr.get("residential")
                        or addr.get("village")
                        or addr.get("hamlet")
                        or ""
                    ).strip()
                    if area and area not in parts:
                        parts.append(area)

                    # Ko'cha nomi
                    road = (
                        addr.get("road")
                        or addr.get("pedestrian")
                        or addr.get("footway")
                        or addr.get("street")
                        or ""
                    ).strip()
                    if road and road not in parts:
                        parts.append(road)

                    # Uy raqami yoki bino/mo'ljal nomi
                    poi = (
                        addr.get("amenity")
                        or addr.get("shop")
                        or addr.get("building")
                        or addr.get("office")
                        or data.get("name")
                        or ""
                    ).strip()
                    house = (addr.get("house_number") or "").strip()
                    if house:
                        parts.append(f"{house}-uy")
                    elif poi and poi not in parts:
                        parts.append(poi)

                    if parts:
                        place_name = ", ".join(parts)
                    else:
                        disp = (data.get("display_name") or "").strip()
                        if disp:
                            clean_parts = [
                                p.strip() for p in disp.split(",")
                                if p.strip() and not p.strip().isdigit() and "oʻzbekiston" not in p.lower() and "uzbekistan" not in p.lower()
                            ]
                            if clean_parts:
                                place_name = ", ".join(clean_parts[:3])
    except Exception as e:
        log.warning(f"Nominatim reverse geocode warning: {e}")

    # 2-usul (Fallback): BigDataCloud Reverse Geocode API
    if not place_name:
        bdc_url = (
            f"https://api.bigdatacloud.net/data/reverse-geocode-client"
            f"?latitude={lat_f}&longitude={lon_f}&localityLanguage=uz"
        )
        try:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                async with session.get(bdc_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        bdata = await resp.json()
                        bparts = []
                        for k in ("city", "locality", "principalSubdivision"):
                            v = (bdata.get(k) or "").strip()
                            if v and v not in bparts:
                                bparts.append(v)
                        if bparts:
                            place_name = ", ".join(bparts)
        except Exception:
            pass

    if not place_name:
        place_name = "Xaritada belgilangan manzil"

    _PLACE_CACHE[cache_key] = (place_name, now)
    return place_name


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


def get_delivery_start_keyboard(order_id: int, is_eat_in: bool = False) -> InlineKeyboardMarkup:
    """
    -1003943860489 (Yetkazib berish / Kuryer kanali) yoki Kafe kanali uchun 1-bosqich tugmasi:
    Kuryer yo'lga chiqqanda yoki «Shu yerda» buyurtmasi tayyor bo'lganda bosiladi.
    """
    markup = InlineKeyboardMarkup(row_width=1)
    btn_text = (
        "🍽 Buyurtma tayyorlandi (Stolga olib chiqish)"
        if is_eat_in
        else "🛵 Yo'lga chiqish (Yetkazishni boshlash)"
    )
    markup.add(
        InlineKeyboardButton(
            btn_text,
            callback_data=f"dlv_start_{order_id}"
        )
    )
    return markup


def get_delivery_complete_keyboard(order_id: int, is_eat_in: bool = False) -> InlineKeyboardMarkup:
    """
    -1003943860489 (Yetkazib berish / Kuryer kanali) yoki Kafe kanali uchun 2-bosqich tugmasi:
    1-tugma bosilgandan keyin avtomatik shu tugmaga aylanadi.
    """
    markup = InlineKeyboardMarkup(row_width=1)
    btn_text = (
        "✅ Buyurtma yetkazildi (Stolga topshirildi)"
        if is_eat_in
        else "✅ Buyurtma yetkazildi (Mijozga topshirildi)"
    )
    markup.add(
        InlineKeyboardButton(
            btn_text,
            callback_data=f"dlv_finish_{order_id}"
        )
    )
    return markup


async def notify_admins_new_order(bot, order_id, total_amount, user, items, phone, address,
                                   location=None, note=None, delivery_type="delivery",
                                   payment_method="Naqd (Yetkazib berilganda)",
                                   promo_code=None, discount_pct=0, discount_amt=0,
                                   branch_name=None, distance_km=None, target_channel_id=None):
    """
    Mijoz buyurtma qilganda:
      1. Eng yaqin filialning `admin_chat_id` (yoki ADMIN_CHANNEL_ID) kanaliga yuboriladi
         (✅ Buyurtmani qabul qilish / ❌ Bekor qilish tugmalari bilan).
      2. DELIVERY_CHANNEL_ID (-1003943860489) ga bu bosqichda YUBORILMAYDI!
         Faqat kanalda "Qabul qilish" bosilgandagina yuboriladi.
    """
    is_delivery = (delivery_type == "delivery" and
                   not (address and "Stol raqami" in str(address)))

    if is_delivery:
        order_type_emoji = "🛵"
        order_type_label = "Yetkazib berish"
    else:
        order_type_emoji = "🍽️"
        order_type_label = "Shu yerda"

    loc_lat = location.get("lat") if isinstance(location, dict) else None
    loc_lon = location.get("lon") if isinstance(location, dict) else None
    address_label = await resolve_human_address(address, loc_lat, loc_lon) if is_delivery else (address or "—")

    # Agar target_channel_id berilmagan bo'lsa, filialni avtomatik aniqlab
    # 1-filial (-1003885234768) yoki 2-filial (-1003631903801) kanaliga yo'naltiramiz
    if not target_channel_id:
        try:
            from utils.geo_routing import resolve_branch_for_order
            nb = await resolve_branch_for_order(
                client_lat=float(loc_lat) if loc_lat is not None else None,
                client_lon=float(loc_lon) if loc_lon is not None else None,
                address=address_label or address,
            )
            if nb and nb.get("admin_chat_id"):
                target_channel_id = nb.get("admin_chat_id")
        except Exception as e:
            log.warning(f"notify_admins_new_order geo_routing warning: {e}")

    # ── Mahsulotlar va rasmlarni yig'ish ─────────────────────────────
    items_with_price_text = ""
    photo_urls            = []
    items_subtotal        = 0

    for i in items:
        try:
            item_d    = dict(i)
            qty       = item_d.get('quantity', 1)
            price     = item_d.get('price', 0)
            name      = item_d.get('name', 'Mahsulot')
            image_url = item_d.get('image_url')
        except Exception:
            qty, price, name, image_url = 1, 0, "Mahsulot", None

        items_subtotal += price * qty
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

    # ── Promokod haqida ma'lumot (agar qo'llanilgan bo'lsa) ──────────
    promo_block = ""
    if discount_amt and discount_amt > 0:
        code_str = promo_code or "PROMO"
        pct_str  = f" — {discount_pct}%" if discount_pct else ""
        after_disc = max(0, items_subtotal - discount_amt)
        promo_block = (
            f"\n💵 <b>Mahsulotlar narxi:</b> {items_subtotal:,} so'm"
            f"\n🎟 <b>Promokod ({code_str}{pct_str}):</b> -{discount_amt:,} so'm"
            f"\n🏷 <b>Chegirma bilan:</b> {after_disc:,} so'm\n"
        )

    # ── To'lov usuli belgisi ─────────────────────────────────────────
    is_online = payment_method and "Online" in str(payment_method)
    if is_online:
        payment_emoji = "💳"
        payment_label = "Karta orqali to'landi (Click/Payme)"
    else:
        payment_emoji = "💵"
        payment_label = "Naqd pul (Yetkazib berilganda)"

    # ── 1. KAFE KANALI (1-filial: -1003885234768 yoki 2-filial: -1003631903801) ──
    channel_to_send = target_channel_id or ADMIN_CHANNEL_ID
    if channel_to_send:
        loc_title = "📍 <b>Manzil:</b>" if is_delivery else "🪑 <b>Stol:</b>"
        cafe_channel_msg = (
            f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
            f"⏳ <i>Holat: Kafe tasdiqlashi kutilmoqda...</i>\n\n"
            f"👤 <b>Mijoz:</b> {full_name} {username_text}\n"
            f"📞 <b>Telefon:</b> {phone_display}\n"
            f"{order_type_emoji} <b>Turi:</b> {order_type_label}\n"
            f"{loc_title} {address_label}"
            f"{note_text}\n\n"
            f"🍛 <b>Buyurtma tarkibi:</b>\n{items_with_price_text}"
            f"{promo_block}\n"
            f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm\n"
            f"{payment_emoji} <b>To'lov:</b> {payment_label}"
        )
        approval_kb = get_cafe_approval_keyboard(order_id)
        try:
            sent_msg = await asyncio.wait_for(
                _send_to_channel(
                    bot, channel_to_send,
                    cafe_channel_msg,
                    unique_photos,
                    send_location=False,
                    reply_markup=approval_kb,
                ),
                timeout=_CHANNEL_TIMEOUT
            )
            # Mijoz 1 daqiqa ichida bekor qilsa, shu xabar yangilanadi
            from utils.order_cancel import register_channel_message, mark_if_already_cancelled
            register_channel_message(order_id, sent_msg)
            await mark_if_already_cancelled(bot, order_id)
        except Exception as e:
            log.error(f"ADMIN_CHANNEL_ID ({channel_to_send}) ga yuborishda xato: {e}")


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
        promo_code     = order_d.get("promo_code")
        discount_amt   = order_d.get("discount_amount") or 0

        is_delivery = (delivery_type == "delivery" and
                       not (address and "Stol raqami" in str(address)))

        if is_delivery:
            address = await resolve_human_address(address, lat, lon)

        if is_delivery:
            header_line = f"🛵 <b>Yetkazib berish #{order_id}</b>"
        else:
            header_line = f"🍽️ <b>Shu yerda #{order_id}</b>"

        items_with_price_text = ""
        photo_urls = []
        items_subtotal = 0

        for i in items:
            qty       = i.get("quantity", 1)
            price     = i.get("price_at_time") or i.get("price") or 0
            name      = i.get("name") or "Mahsulot"
            image_url = i.get("image_url")
            items_subtotal += price * qty
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

        promo_block = ""
        if discount_amt and discount_amt > 0:
            code_str = promo_code or "PROMO"
            after_disc = max(0, items_subtotal - discount_amt)
            promo_block = (
                f"\n💵 <b>Mahsulotlar narxi:</b> {items_subtotal:,} so'm"
                f"\n🎟 <b>Promokod ({code_str}):</b> -{discount_amt:,} so'm"
                f"\n🏷 <b>Chegirma bilan:</b> {after_disc:,} so'm\n"
            )

        is_online = payment_method and "Online" in str(payment_method)
        if is_online:
            payment_emoji = "💳"
            payment_label = "Karta orqali to'landi (Click/Payme)"
        else:
            payment_emoji = "💵"
            payment_label = "Naqd pul (Yetkazib berilganda)"

        loc_title = "📍 <b>Manzil:</b>" if is_delivery else "🪑 <b>Stol:</b>"

        delivery_msg = (
            f"{header_line}\n"
            f"✅ <i>Kafe tomonidan qabul qilindi</i>\n\n"
            f"👤 <b>Mijoz:</b> {full_name} {username_text}\n"
            f"📞 <b>Telefon:</b> {phone_display}\n"
            f"{loc_title} {address}"
            f"{note_text}\n\n"
            f"🍛 <b>Buyurtma tarkibi:</b>\n{items_with_price_text}"
            f"{promo_block}\n"
            f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm\n"
            f"{payment_emoji} <b>To'lov:</b> {payment_label}"
        )

        delivery_kb = get_delivery_start_keyboard(order_id, is_eat_in=not is_delivery)

        await asyncio.wait_for(
            _send_to_channel(
                bot,
                DELIVERY_CHANNEL_ID,
                delivery_msg,
                unique_photos,
                send_location=bool(is_delivery and lat and lon),
                lat=lat,
                lon=lon,
                reply_markup=delivery_kb,
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
    Qaytaradi: reply_markup biriktirilgan asosiy xabar (yoki None).
    """
    main_msg = None
    if not photo_urls:
        main_msg = await bot.send_message(channel_id, caption, parse_mode="HTML", reply_markup=reply_markup)
    elif len(photo_urls) == 1:
        main_msg = await _safe_send_photo(bot, channel_id, photo_urls[0], caption, reply_markup=reply_markup)
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
            main_msg = await bot.send_message(channel_id, caption, parse_mode="HTML", reply_markup=reply_markup)
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

    return main_msg


async def _safe_send_photo(bot, channel_id, photo_url: str, caption: str, reply_markup=None):
    """Rasmni xavfsiz yuborish — ishlamasa faqat matn."""
    try:
        return await bot.send_photo(
            channel_id, photo=photo_url,
            caption=caption, parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception:
        return await bot.send_message(channel_id, caption, parse_mode="HTML", reply_markup=reply_markup)
