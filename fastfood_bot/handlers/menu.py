from aiogram import types, Dispatcher
from database.crud import (
    get_categories, get_products_by_category, get_product,
    search_products, toggle_favorite, is_favorite as check_is_favorite,
    get_user_language, get_product_name, get_product_desc, _field
)
from keyboards.product_keyboard import get_categories_markup, get_product_markup
from utils.states import SearchStates
from utils.i18n import get_text
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


async def show_menu(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    categories = await get_categories()
    if not categories:
        await message.answer(get_text("menu_empty", lang))
        return
    await message.answer(
        get_text("menu_title", lang),
        reply_markup=get_categories_markup(categories, lang=lang),
        parse_mode="HTML"
    )


async def show_category_products(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    try:
        category_id = int(call.data.split("_")[1])
        products = await get_products_by_category(category_id)

        if not products:
            await call.answer(get_text("category_empty", lang), show_alert=True)
            return

        await call.message.delete()
        await show_product_page(call, products[0], category_id, 0, len(products))
    except Exception as e:
        import logging
        logging.error(f"show_category_products xato: {e}")
        await call.answer("⚠️ Xatolik yuz berdi, qayta urinib ko'ring.", show_alert=True)
        return
    await call.answer()


async def paginate_products(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    try:
        data = call.data.split("_")
        category_id = int(data[1])
        index = int(data[2])

        products = await get_products_by_category(category_id)
        if not products or index < 0 or index >= len(products):
            await call.answer(get_text("no_more_products", lang))
            return

        await show_product_page(call, products[index], category_id, index, len(products), is_edit=True)
    except Exception as e:
        import logging
        logging.error(f"paginate_products xato: {e}")
        await call.answer("⚠️ Xatolik yuz berdi.", show_alert=True)
        return
    await call.answer()


async def show_product_page(call, product, category_id, index, total_products, quantity=1, is_edit=False):
    lang = await get_user_language(call.from_user.id)

    # old_price — xavfsiz olish
    try:
        old_price = _field(product, 'old_price')
    except Exception:
        old_price = None

    # Nom va tavsif tanlangan tilda (xato bo'lsa o'zbek)
    prod_name = get_product_name(product, lang)
    prod_desc = get_product_desc(product, lang)

    caption = f"<b>{prod_name}</b>\n\n"
    if prod_desc:
        caption += f"{prod_desc}\n\n"

    if old_price and old_price > product['price']:
        caption += get_text("price_discount_label", lang, old=old_price, new=product['price'])
    else:
        caption += get_text("price_label", lang, price=product['price'])

    fav = False
    try:
        if hasattr(call, 'from_user') and call.from_user:
            fav = await check_is_favorite(call.from_user.id, product['id'])
    except Exception:
        pass
    markup = get_product_markup(product['id'], category_id, index, total_products, quantity, is_favorite=fav, lang=lang)

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
            await message.answer_photo(
                photo=product['image_url'], caption=caption,
                reply_markup=markup, parse_mode="HTML"
            )
        except Exception:
            await message.answer(caption, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=markup, parse_mode="HTML")


async def back_to_categories(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    try:
        await call.message.delete()
    except Exception:
        pass
    categories = await get_categories()
    await call.message.answer(
        get_text("menu_title", lang),
        reply_markup=get_categories_markup(categories, lang=lang),
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
        fav = await check_is_favorite(call.from_user.id, product_id)
        lang2 = await get_user_language(call.from_user.id)
        await call.message.edit_reply_markup(
            reply_markup=get_product_markup(
                product_id, category_id, current_index, total_products, new_qty, is_favorite=fav, lang=lang2
            )
        )

    await call.answer()


async def noop_handler(call: types.CallbackQuery):
    await call.answer()


# ── Qidiruv ──────────────────────────────────────────────────────────

async def start_search(message: types.Message):
    lang = await get_user_language(message.from_user.id)
    await SearchStates.waiting_query.set()
    await message.answer(
        get_text("search_ask", lang),
        parse_mode="HTML"
    )


async def process_search(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    if message.text.strip().lower() == "/bekor":
        await state.finish()
        await message.answer(get_text("search_cancelled", lang))
        return

    query = message.text.strip()
    results = await search_products(query)
    await state.finish()

    if not results:
        await message.answer(
            get_text("search_no_results", lang, query=query),
            parse_mode="HTML"
        )
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for p in results:
        p_name = get_product_name(p, lang)
        old_price = p.get('old_price')
        if old_price and old_price > p['price']:
            label = get_text("search_item_label", lang, icon="🏷", name=p_name, price=p['price'])
        else:
            label = get_text("search_item_label", lang, icon="🍴", name=p_name, price=p['price'])
        markup.add(InlineKeyboardButton(label, callback_data=f"search_prod_{p['id']}_{p['category_id']}"))

    await message.answer(
        get_text("search_results", lang, query=query, count=len(results)),
        reply_markup=markup,
        parse_mode="HTML"
    )


async def search_product_callback(call: types.CallbackQuery):
    lang = await get_user_language(call.from_user.id)
    parts = call.data.split("_")
    product_id = int(parts[2])
    category_id = int(parts[3])

    product = await get_product(product_id)
    if not product:
        await call.answer(get_text("product_not_found", lang), show_alert=True)
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
    lang = await get_user_language(call.from_user.id)
    parts = call.data.split("_")
    product_id = int(parts[1])
    category_id = int(parts[2])
    index = int(parts[3])
    added = await toggle_favorite(call.from_user.id, product_id)
    if added:
        await call.answer(get_text("fav_added", lang), show_alert=True)
    else:
        await call.answer(get_text("fav_removed", lang), show_alert=True)
    products = await get_products_by_category(category_id)
    if products and 0 <= index < len(products):
        await show_product_page(call, products[index], category_id, index, len(products), is_edit=True)


def register_menu_handlers(dp: Dispatcher):
    _MENU_TEXTS = ["🍽 Menu", "🍽 Menyu", "🍽 Меню"]
    _SEARCH_TEXTS = ["🔍 Izlash", "🔍 Поиск", "🔍 Search"]
    dp.register_message_handler(show_menu, lambda m: m.text in _MENU_TEXTS)
    dp.register_callback_query_handler(show_category_products, lambda c: c.data.startswith('category_'))
    dp.register_callback_query_handler(paginate_products, lambda c: c.data.startswith('paginate_'))
    dp.register_callback_query_handler(back_to_categories, text="back_to_categories")
    dp.register_callback_query_handler(
        change_quantity,
        lambda c: c.data.startswith('plus_') or c.data.startswith('minus_')
    )
    dp.register_callback_query_handler(noop_handler, text="noop")
    dp.register_callback_query_handler(toggle_fav_handler, lambda c: c.data.startswith('fav_'), state="*")
    dp.register_message_handler(start_search, lambda m: m.text in _SEARCH_TEXTS, state="*")
    dp.register_message_handler(process_search, state=SearchStates.waiting_query)
    dp.register_callback_query_handler(
        search_product_callback, lambda c: c.data.startswith('search_prod_'), state="*"
    )
