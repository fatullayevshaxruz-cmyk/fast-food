from aiogram import types, Dispatcher
from database.crud import get_categories, get_products_by_category, get_product, search_products, toggle_favorite, is_favorite as check_is_favorite
from keyboards.product_keyboard import get_categories_markup, get_product_markup
from utils.states import SearchStates
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def show_menu(message: types.Message):
    categories = await get_categories()
    if not categories:
        await message.answer("Hozircha menu bo'sh.")
        return
        
    await message.answer(
        "🍽 <b>Menumiz</b>\n"
        "Quyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_categories_markup(categories),
        parse_mode="HTML"
    )

async def show_category_products(call: types.CallbackQuery):
    category_id = int(call.data.split("_")[1])
    products = await get_products_by_category(category_id)
    
    if not products:
        await call.answer("Bu kategoriyada mahsulotlar yo'q.", show_alert=True)
        return

    await call.message.delete()
    await show_product_page(call, products[0], category_id, 0, len(products))
    await call.answer()

async def paginate_products(call: types.CallbackQuery):
    data = call.data.split("_")
    category_id = int(data[1])
    index = int(data[2])
    
    products = await get_products_by_category(category_id)
    if not products or index < 0 or index >= len(products):
        await call.answer("Boshqa mahsulot yo'q")
        return

    await show_product_page(call, products[index], category_id, index, len(products), is_edit=True)
    await call.answer()

async def show_product_page(call, product, category_id, index, total_products, quantity=1, is_edit=False):
    # Chegirma bor-yo'qligini tekshirish
    old_price = product.get('old_price') if isinstance(product, dict) else (product['old_price'] if 'old_price' in product.keys() else None)
    
    caption = f"<b>{product['name']}</b>\n\n"
    if product['description']:
        caption += f"{product['description']}\n\n"
    
    if old_price and old_price > product['price']:
        caption += f"💵 <s>{old_price:,} so'm</s> → <b>{product['price']:,} so'm</b> 🏷"
    else:
        caption += f"💵 Narxi: <b>{product['price']:,} so'm</b>"
    
    # Sevimli ekanligini tekshirish
    fav = False
    if hasattr(call, 'from_user') and call.from_user:
        fav = await check_is_favorite(call.from_user.id, product['id'])
    markup = get_product_markup(product['id'], category_id, index, total_products, quantity, is_favorite=fav)
    
    if is_edit:
        try:
            if product['image_url']:
                media = types.InputMediaPhoto(media=product['image_url'], caption=caption, parse_mode="HTML")
                await call.message.edit_media(media, reply_markup=markup)
            else:
                await call.message.edit_text(caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            try:
                await call.message.delete()
            except Exception:
                pass
            await _send_product(call.message, product, caption, markup)
    else:
        await _send_product(call.message, product, caption, markup)


async def _send_product(message, product, caption, markup):
    """Mahsulotni xavfsiz yuborish."""
    if product['image_url']:
        try:
            await message.answer_photo(photo=product['image_url'], caption=caption, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await message.answer(f"🖼 Rasm yuklanmadi.\n\n{caption}", reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=markup, parse_mode="HTML")


async def back_to_categories(call: types.CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    categories = await get_categories()
    await call.message.answer(
        "🍽 <b>Menumiz</b>\n"
        "Quyidagi kategoriyalardan birini tanlang:",
        reply_markup=get_categories_markup(categories),
        parse_mode="HTML"
    )

async def change_quantity(call: types.CallbackQuery):
    parts = call.data.split("_")
    action = parts[0]
    product_id = int(parts[1])
    current_qty = int(parts[2])
    category_id = int(parts[3])
    current_index = int(parts[4])
    
    products = await get_products_by_category(category_id)
    total_products = len(products)
    
    new_qty = current_qty
    if action == "plus":
        new_qty += 1
    elif action == "minus":
        if current_qty > 1:
            new_qty -= 1
            
    if new_qty != current_qty:
        # Sevimlilar holatini DB dan tekshiramiz
        fav = await check_is_favorite(call.from_user.id, product_id)
        await call.message.edit_reply_markup(
            reply_markup=get_product_markup(product_id, category_id, current_index, total_products, new_qty, is_favorite=fav)
        )
    
    await call.answer()

async def noop_handler(call: types.CallbackQuery):
    await call.answer()


# ── Qidiruv ──────────────────────────────────────────────────────────

async def start_search(message: types.Message):
    """Qidiruv boshlash."""
    await SearchStates.waiting_query.set()
    await message.answer(
        "🔍 <b>Mahsulot izlash</b>\n\n"
        "Mahsulot nomini yozing:\n"
        "<i>(Bekor qilish: /bekor)</i>",
        parse_mode="HTML"
    )

async def process_search(message: types.Message, state: FSMContext):
    """Qidiruv natijalarini ko'rsatish."""
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer("❌ Qidiruv bekor qilindi.")
        return

    query = message.text.strip()
    results = await search_products(query)
    await state.finish()

    if not results:
        await message.answer(
            f"😔 <b>\"{query}\"</b> bo'yicha hech narsa topilmadi.\n"
            "Boshqa nom bilan qaytadan izlab ko'ring.",
            parse_mode="HTML"
        )
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for p in results:
        cat_name = p.get('category_name', '')
        old_price = p.get('old_price')
        if old_price and old_price > p['price']:
            label = f"🏷 {p['name']} — {p['price']:,} so'm"
        else:
            label = f"🍴 {p['name']} — {p['price']:,} so'm"
        markup.add(InlineKeyboardButton(label, callback_data=f"search_prod_{p['id']}_{p['category_id']}"))

    await message.answer(
        f"🔍 <b>\"{query}\"</b> bo'yicha <b>{len(results)}</b> ta natija:\n",
        reply_markup=markup,
        parse_mode="HTML"
    )

async def search_product_callback(call: types.CallbackQuery):
    """Qidiruv natijasidan mahsulotni tanlash."""
    parts = call.data.split("_")
    product_id = int(parts[2])
    category_id = int(parts[3])

    product = await get_product(product_id)
    if not product:
        await call.answer("Mahsulot topilmadi.", show_alert=True)
        return

    try:
        await call.message.delete()
    except Exception:
        pass

    products = await get_products_by_category(category_id)
    index = 0
    for i, p in enumerate(products):
        if p['id'] == product_id:
            index = i
            break

    await show_product_page(call, product, category_id, index, len(products) if products else 1)
    await call.answer()


async def toggle_fav_handler(call: types.CallbackQuery):
    """Sevimli qo'shish/olib tashlash."""
    parts = call.data.split("_")
    product_id = int(parts[1])
    category_id = int(parts[2])
    index = int(parts[3])
    added = await toggle_favorite(call.from_user.id, product_id)
    if added:
        await call.answer("❤️ Sevimlilarga qo'shildi!", show_alert=True)
    else:
        await call.answer("💔 Sevimlilardan olib tashlandi.", show_alert=True)
    # Sahifani yangilash
    products = await get_products_by_category(category_id)
    if products and 0 <= index < len(products):
        await show_product_page(call, products[index], category_id, index, len(products), is_edit=True)


def register_menu_handlers(dp: Dispatcher):
    dp.register_message_handler(show_menu, text="🍽 Menu")
    dp.register_callback_query_handler(show_category_products, lambda c: c.data.startswith('category_'))
    dp.register_callback_query_handler(paginate_products, lambda c: c.data.startswith('paginate_'))
    dp.register_callback_query_handler(back_to_categories, text="back_to_categories")
    dp.register_callback_query_handler(change_quantity, lambda c: c.data.startswith('plus_') or c.data.startswith('minus_'))
    dp.register_callback_query_handler(noop_handler, text="noop")
    dp.register_callback_query_handler(toggle_fav_handler, lambda c: c.data.startswith('fav_'), state="*")
    # Qidiruv
    dp.register_message_handler(start_search, text="🔍 Izlash", state="*")
    dp.register_message_handler(process_search, state=SearchStates.waiting_query)
    dp.register_callback_query_handler(search_product_callback, lambda c: c.data.startswith('search_prod_'), state="*")
