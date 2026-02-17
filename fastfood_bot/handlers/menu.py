from aiogram import types, Dispatcher
from database.crud import get_categories, get_products_by_category, get_product
from keyboards.product_keyboard import get_categories_markup, get_product_markup

async def show_menu(message: types.Message):
    categories = await get_categories()
    if not categories:
        await message.answer("Hozircha menu bo'sh.")
        return
        
    await message.answer(
        "🍽 **Menumiz**\n"
        "Quyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_categories_markup(categories)
    )

async def show_category_products(call: types.CallbackQuery):
    category_id = int(call.data.split("_")[1])
    products = await get_products_by_category(category_id)
    
    if not products:
        await call.answer("Bu kategoriyada mahsulotlar yo'q.", show_alert=True)
        return

    await call.message.delete()
    
    # Show first product
    await show_product_page(call, products[0], category_id, 0, len(products))
    await call.answer()

async def paginate_products(call: types.CallbackQuery):
    # data: paginate_{category_id}_{index}
    data = call.data.split("_")
    category_id = int(data[1])
    index = int(data[2])
    
    products = await get_products_by_category(category_id)
    if not products or index < 0 or index >= len(products):
        await call.answer("Boshqa mahsulot yo'q")
        return

    await show_product_page(call, products[index], category_id, index, len(products), is_edit=True)
    await call.answer()

async def show_product_page(call: types.CallbackQuery, product, category_id, index, total_products, quantity=1, is_edit=False):
    caption = (
        f"<b>{product['name']}</b>\n\n"
        f"{product['description'] or ''}\n\n"
        f"💵 Narxi: {product['price']:,} so'm"
    )
    markup = get_product_markup(product['id'], category_id, index, total_products, quantity)
    
    if is_edit:
        try:
            if product['image_url']:
                media = types.InputMediaPhoto(media=product['image_url'], caption=caption, parse_mode="HTML")
                await call.message.edit_media(media, reply_markup=markup)
            else:
                # If no image, but we need to edit.. 
                # Ideally we shouldn't have mixed types if possible, or delete/send
                await call.message.delete()
                await call.message.answer(caption, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            # If edit fails (e.g. invalid photo or same content), try delete/send
            try:
                await call.message.delete()
            except:
                pass
            
            if product['image_url']:
                try:
                    await call.message.answer_photo(photo=product['image_url'], caption=caption, reply_markup=markup, parse_mode="HTML")
                except Exception as e:
                    print(f"Failed to send image: {e}")
                    await call.message.answer(f"🖼 Rasm yuklanmadi.\n\n{caption}", reply_markup=markup, parse_mode="HTML")
            else:
                await call.message.answer(caption, reply_markup=markup, parse_mode="HTML")
    else:
        if product['image_url']:
            try:
                await call.message.answer_photo(photo=product['image_url'], caption=caption, reply_markup=markup, parse_mode="HTML")
            except Exception as e:
                print(f"Failed to send image: {e}")
                await call.message.answer(f"🖼 Rasm yuklanmadi.\n\n{caption}", reply_markup=markup, parse_mode="HTML")
        else:
            await call.message.answer(caption, reply_markup=markup, parse_mode="HTML")


async def back_to_categories(call: types.CallbackQuery):
    await call.message.delete()
    categories = await get_categories()
    await call.message.answer(
        "🍽 **Menumiz**\n"
        "Quyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_categories_markup(categories)
    )

async def change_quantity(call: types.CallbackQuery):
    # data: action_productid_quantity_catid_index
    parts = call.data.split("_")
    action = parts[0]
    product_id = int(parts[1])
    current_qty = int(parts[2])
    category_id = int(parts[3])
    current_index = int(parts[4])
    
    # We need total products count for the markup
    products = await get_products_by_category(category_id)
    total_products = len(products)
    
    new_qty = current_qty
    if action == "plus":
        new_qty += 1
    elif action == "minus":
        if current_qty > 1:
            new_qty -= 1
            
    if new_qty != current_qty:
        await call.message.edit_reply_markup(
            reply_markup=get_product_markup(product_id, category_id, current_index, total_products, new_qty)
        )
    
    await call.answer()

async def noop_handler(call: types.CallbackQuery):
    await call.answer(f"Tanlangan son: {call.data.split('_')[1]}", show_alert=False) # split logic might differ based on call data usage

def register_menu_handlers(dp: Dispatcher):
    dp.register_message_handler(show_menu, text="🍽 Menu")
    dp.register_callback_query_handler(show_category_products, lambda c: c.data.startswith('category_'))
    dp.register_callback_query_handler(paginate_products, lambda c: c.data.startswith('paginate_'))
    dp.register_callback_query_handler(back_to_categories, text="back_to_categories")
    dp.register_callback_query_handler(change_quantity, lambda c: c.data.startswith('plus_') or c.data.startswith('minus_'))
    dp.register_callback_query_handler(noop_handler, text="noop")
