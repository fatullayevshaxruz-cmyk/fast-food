import asyncio
from aiogram import Bot, types
from config import BOT_TOKEN, ADMIN_CHANNEL_ID

async def test_media_group():
    bot = Bot(token=BOT_TOKEN)
    channel_id = ADMIN_CHANNEL_ID
    
    print(f"Testing MediaGroup to channel: {channel_id}")

    # Dummy data
    items = [
        {'name': 'Test Lavash', 'price': 25000, 'quantity': 2, 'image_url': 'https://www.themealdb.com/images/media/meals/xquakq1619787532.jpg'},
        {'name': 'Test Burger', 'price': 30000, 'quantity': 1, 'image_url': 'https://www.themealdb.com/images/media/meals/utxwwp1511381813.jpg'},
        {'name': 'No Image Food', 'price': 10000, 'quantity': 5, 'image_url': None}
    ]
    
    total_amount = sum(i['price'] * i['quantity'] for i in items)
    items_text = "\n".join([f"▫️ {i['name']} x {i['quantity']}" for i in items])
    
    full_message = (
        f"🆕 <b>Test Buyurtma #999</b>\n"
        f"👤 <b>Mijoz:</b> Test User\n"
        f"📞 <b>Telefon:</b> +998901234567\n"
        f"📍 <b>Manzil:</b> Test Address\n\n"
        f"🍛 <b>Buyurtma tarkibi:</b>\n{items_text}\n\n"
        f"💰 <b>Umumiy summa:</b> {total_amount:,} so'm"
    )

    import aiohttp
    from io import BytesIO

    try:
        media = types.MediaGroup()
        has_images = False
        
        async with aiohttp.ClientSession() as session:
            for item in items:
                image_url = item.get('image_url')
                if image_url:
                    try:
                        async with session.get(image_url) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                # Use InputFile or just bytes
                                photo_file = BytesIO(data)
                                photo_file.name = f"image_{item['name']}.jpg" # important for input file
                                
                                if not has_images:
                                    media.attach_photo(photo_file, caption=full_message, parse_mode="HTML")
                                    has_images = True
                                else:
                                    media.attach_photo(photo_file)
                            else:
                                print(f"Failed to download image: {image_url} Status: {resp.status}")
                    except Exception as download_err:
                        print(f"Error downloading {image_url}: {download_err}")
        
        if has_images:
            print("Sending media group (as uploaded files)...")
            await bot.send_media_group(channel_id, media=media)
            print("Media group sent successfully!")
        else:
            print("No images to send.")
            await bot.send_message(channel_id, full_message, parse_mode="HTML")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILED to send media group: {e}")
        # Try fallback
        try:
            print("Attempting fallback text message...")
            await bot.send_message(channel_id, full_message, parse_mode="HTML")
            print("Fallback text sent.")
        except Exception as e2:
            print(f"Fallback failed: {e2}")

    await bot.close()

if __name__ == "__main__":
    asyncio.run(test_media_group())
