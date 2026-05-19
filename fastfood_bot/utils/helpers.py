from config import ADMIN_ID, ADMIN_CHANNEL_ID
import aiohttp
from io import BytesIO
from aiogram import types

async def notify_admins_new_order(bot, order_id, total_amount, user, items, phone, address, location=None, note=None):
    # 1. Notify ADMIN_ID (Just Food Items)
    items_text = "\n".join([f"▫️ {i['name']} x {i['quantity']}" for i in items])
    note_text = f"\n📝 <b>Izoh:</b> <i>{note}</i>" if note else ""
    
    phone_display = phone or "ko'rsatilmagan"
    if address and "Stol raqami" in address:
        admin_message = (
            f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
            f"🍽️ <b>Shu yerda:</b> {address}\n\n"
            f"🍛 <b>Buyurtma:</b>\n{items_text}\n"
            f"💰 <b>Jami:</b> {total_amount:,} so'm"
            f"{note_text}"
        )
    else:
        admin_message = (
            f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
            f"🛵 <b>Yetkazib berish</b>\n"
            f"📞 Telefon: {phone_display}\n\n"
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

    # 2. Notify ADMIN_CHANNEL_ID (Full Details)
    if ADMIN_CHANNEL_ID:
        username_text = f"(@{user.username})" if user.username else ""
        
        # Buyurtma turini aniqlash
        if address and "Stol raqami" in address:
            order_type_text = "🍽️ <b>Turi:</b> Shu yerda"
            address_text = f"📍 <b>Joy:</b> {address}"
        else:
            order_type_text = "🛵 <b>Turi:</b> Olib ketish (Yetkazish)"
            address_text = f"📍 <b>Manzil:</b> {address}"
        
        full_message = (
            f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
            f"👤 <b>Mijoz:</b> {user.full_name} {username_text}\n"
            f"📞 <b>Telefon:</b> {phone_display}\n"
            f"{order_type_text}\n"
            f"{address_text}\n"
            f"{note_text}\n\n"
            f"🍛 <b>Buyurtma tarkibi:</b>\n{items_text}\n\n"
            f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm"
        )
        try:
            media = types.MediaGroup()
            has_images = False
            
            async with aiohttp.ClientSession() as session:
                for index, item in enumerate(items):
                    image_url = item.get('image_url') if isinstance(item, dict) else None
                    if not image_url:
                        try:
                            image_url = item['image_url']
                        except (KeyError, IndexError):
                            image_url = None
                    
                    if image_url:
                        try:
                            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                                if resp.status == 200:
                                    ct = resp.headers.get('Content-Type', '')
                                    if 'image' in ct:
                                        data = await resp.read()
                                        photo_file = BytesIO(data)
                                        photo_file.name = f"img_{index}.jpg"
                                        
                                        if not has_images:
                                            media.attach_photo(photo_file, caption=full_message, parse_mode="HTML")
                                            has_images = True
                                        else:
                                            media.attach_photo(photo_file)
                        except Exception:
                            pass
            
            if has_images:
                await bot.send_media_group(ADMIN_CHANNEL_ID, media=media)
            else:
                await bot.send_message(ADMIN_CHANNEL_ID, full_message, parse_mode="HTML")

            if location and location.get('lat') and location.get('lon'):
                await bot.send_location(ADMIN_CHANNEL_ID, latitude=location['lat'], longitude=location['lon'])
        except Exception as e:
            print(f"Failed to send to channel: {e}")
            try:
                await bot.send_message(ADMIN_CHANNEL_ID, full_message, parse_mode="HTML")
            except Exception:
                pass
