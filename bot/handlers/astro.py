from datetime import datetime, timezone, timedelta
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services import limit_service, claude_service
from bot.services.card_engine import card_engine
from bot.keyboards.inline import back_to_menu, paywall_menu

router = Router()

PAYWALL_TEXT = (
    "🌙 Персональный гороскоп доступен в Pro-подписке.\n\n"
    "Звёзды говорят каждый день — но не со всеми одинаково."
)


@router.callback_query(F.data == "horoscope")
async def daily_horoscope(callback: CallbackQuery, bot: Bot) -> None:
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, callback.from_user.id)
        can = await limit_service.can_do_horoscope(session, user.telegram_id, user.is_pro)

    if not user.zodiac_sign:
        await callback.answer("Сначала укажи знак зодиака в настройках", show_alert=True)
        return

    if not can:
        await callback.message.edit_text(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
        return

    await bot.send_chat_action(callback.message.chat.id, "typing")
    msk = timezone(timedelta(hours=3))
    today = datetime.now(msk).strftime("%d %B %Y")
    name = user.name or callback.from_user.first_name or "незнакомка"

    text = await claude_service.daily_horoscope(name, user.zodiac_sign, today)

    async with async_session_factory() as session:
        await limit_service.use_horoscope(session, user.telegram_id)

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=back_to_menu())


@router.callback_query(F.data == "card_of_day")
async def card_of_day(callback: CallbackQuery, bot: Bot) -> None:
    await bot.send_chat_action(callback.message.chat.id, "typing")
    msk = timezone(timedelta(hours=3))
    today = datetime.now(msk).strftime("%d %B %Y")

    card = card_engine.draw(1)[0]
    text = await claude_service.card_of_day(card, today)

    card_header = f"🃏 *{card['name_ru']}*{'  ↓' if card['reversed'] else ''}\n\n"
    await callback.message.edit_text(
        card_header + text,
        parse_mode="Markdown",
        reply_markup=back_to_menu()
    )
