"""
handlers/feedback.py
=====================
Buyurtma yakunlanganda foydalanuvchidan fikr-mulohaza so'rash.

Oqim:
  1. Admin "completed" bosadi → send_feedback_request() chaqiriladi (3 sek delay)
  2. Foydalanuvchi ⭐ 1–5 yulduz bosadi
     - 4–5 ⭐ → "Rahmat!" xabari → tugdi
     - 1–3 ⭐ → Sabab so'raladi (matn yoki /skip)
  3. Sabab yozilsa → DB ga saqlanadi → Adminlarga xabar ketadi
"""

import logging
import asyncio
from aiogram import types, Dispatcher, Bot
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_ID, ADMIN_CHANNEL_ID
from database.crud import get_user_language
from utils.states import FeedbackStates
from utils.i18n import get_text

log = logging.getLogger(__name__)


# ── Feedback so'rovi yuborish ─────────────────────────────────────────

async def send_feedback_request(bot: Bot, user_id: int, order_id: int, lang: str):
    """
    Buyurtma yakunlangandan so'ng ⭐ baholash so'rovi yuboradi.
    admin_change_order_status() dan asyncio.create_task bilan 3 sek delay bilan chaqiriladi.
    """
    try:
        markup = InlineKeyboardMarkup(row_width=5)
        stars_btns = [
            InlineKeyboardButton(
                text="⭐" * i,
                callback_data=f"rating_{order_id}_{i}"
            )
            for i in range(1, 6)
        ]
        markup.add(*stars_btns)

        msg = get_text("feedback_request", lang, id=order_id)
        await bot.send_message(user_id, msg, reply_markup=markup, parse_mode="HTML")

    except Exception as e:
        log.error(f"Feedback so'rovi yuborishda xatolik: {e}")


# ── Yulduz bosildi ────────────────────────────────────────────────────

async def handle_rating(call: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchi yulduz bosdi."""
    try:
        # Tugmalarni o'chirib qo'yish (double-click ni oldini olish)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        parts = call.data.split("_")  # rating_{order_id}_{stars}
        order_id = int(parts[1])
        rating = int(parts[2])
        lang = await get_user_language(call.from_user.id)

        # DB ga saqlash
        from database.crud import save_order_rating
        await save_order_rating(order_id, call.from_user.id, rating)

        if rating >= 4:
            # Yaxshi baho — tugdi
            await call.message.answer(
                get_text("feedback_thanks_high", lang, stars="⭐" * rating),
                parse_mode="HTML"
            )
            await call.answer()
        else:
            # Past baho — sabab so'rash
            await state.update_data(
                feedback_order_id=order_id,
                feedback_rating=rating
            )
            await FeedbackStates.waiting_comment.set()

            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton(
                    get_text("btn_skip", lang),
                    callback_data="feedback_skip"
                )
            )
            await call.message.answer(
                get_text("feedback_ask_comment", lang, stars="⭐" * rating),
                reply_markup=markup,
                parse_mode="HTML"
            )
            await call.answer()

    except Exception as e:
        log.error(f"Rating handleda xatolik: {e}")
        try:
            await call.answer()
        except Exception:
            pass


# ── Sabab matni ───────────────────────────────────────────────────────

async def handle_feedback_text(message: types.Message, state: FSMContext):
    """Foydalanuvchi sabab yozdi."""
    lang = await get_user_language(message.from_user.id)
    data = await state.get_data()
    order_id = data.get("feedback_order_id", 0)
    rating = data.get("feedback_rating", 1)
    comment = message.text.strip() if message.text else None

    # DB ga izoh saqlash
    if comment:
        try:
            from database.crud import update_order_rating_comment
            await update_order_rating_comment(order_id, comment)
        except Exception as e:
            log.error(f"Izoh saqlashda xatolik: {e}")

    await state.finish()
    await message.answer(get_text("feedback_thanks_low", lang), parse_mode="HTML")

    # Adminlarga xabar
    await _notify_admins_bad_rating(
        bot=message.bot,
        user=message.from_user,
        order_id=order_id,
        rating=rating,
        comment=comment,
    )


# ── Inline "O'tkazib yuborish" ────────────────────────────────────────

async def handle_feedback_skip(call: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchi 'O'tkazib yuborish' bosdi."""
    lang = await get_user_language(call.from_user.id)
    await state.finish()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer(get_text("feedback_skipped", lang))


# ── Adminlarga xabar ──────────────────────────────────────────────────

async def _notify_admins_bad_rating(bot, user, order_id, rating, comment):
    """1–3 ⭐ bo'lsa adminlarga ogohlantirish xabari."""
    stars_str = "⭐" * rating
    admin_msg = (
        f"⚠️ <b>Past baholash!</b>\n\n"
        f"📦 Buyurtma #{order_id}\n"
        f"👤 {user.full_name}"
        + (f" (@{user.username})" if user.username else "") + "\n"
        f"⭐ Baho: {stars_str} ({rating}/5)\n"
    )
    if comment:
        admin_msg += f"\n💬 <b>Sabab:</b> <i>{comment}</i>"

    targets = []
    if ADMIN_CHANNEL_ID:
        targets.append(ADMIN_CHANNEL_ID)
    elif ADMIN_ID:
        targets.extend(
            int(a.strip()) for a in ADMIN_ID.split(",") if a.strip()
        )

    for target in targets:
        try:
            await bot.send_message(target, admin_msg, parse_mode="HTML")
        except Exception as e:
            log.error(f"Admin xabari yuborishda xatolik (target={target}): {e}")


# ── Handlerlarni ro'yxatdan o'tkazish ────────────────────────────────

def register_feedback_handlers(dp: Dispatcher):
    """
    Feedback handlerlarini Dispatcher ga ro'yxatdan o'tkazadi.
    bot.py da register_payment_handlers() DAN KEYIN chaqiriladi.
    """
    # Yulduz bosish — har qanday holatda ishlaydi
    dp.register_callback_query_handler(
        handle_rating,
        lambda c: c.data and c.data.startswith("rating_"),
        state="*",
    )

    # Sabab matni — faqat FeedbackStates.waiting_comment holatida
    dp.register_message_handler(
        handle_feedback_text,
        state=FeedbackStates.waiting_comment,
    )

    # "O'tkazib yuborish" inline tugmasi
    dp.register_callback_query_handler(
        handle_feedback_skip,
        text="feedback_skip",
        state=FeedbackStates.waiting_comment,
    )
