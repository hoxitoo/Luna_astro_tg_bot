from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services import limit_service, claude_service
from bot.services.card_engine import card_engine
from bot.keyboards.inline import cancel_button, back_to_menu, tarot_menu, paywall_menu
from bot.utils.text_utils import cards_line

router = Router()

PAYWALL_TEXT = (
    "🌙 Бесплатные расклады на сегодня закончились...\n\n"
    "Ты уже заглянула глубже, чем большинство.\n"
    "Луна готова раскрыть больше — без ограничений.\n\n"
    "✨ *Pro-подписка* открывает:\n"
    "— Безлимитные расклады\n"
    "— Персональный гороскоп каждый день\n"
    "— Расклад на год\n"
    "— Карту дня утром"
)


class TarotFSM(StatesGroup):
    waiting_question_3 = State()
    waiting_question_relations = State()


@router.callback_query(F.data == "tarot_menu")
async def tarot_menu_cb(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🃏 Выбери расклад:",
        reply_markup=tarot_menu()
    )


@router.callback_query(F.data == "tarot_3")
async def tarot_3_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, callback.from_user.id)
        can = await limit_service.can_do_tarot(session, user)
        remaining = await limit_service.remaining_tarot(session, user)

    if not can:
        await callback.message.edit_text(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
        return

    await state.set_state(TarotFSM.waiting_question_3)
    is_pro = limit_service.is_pro_active(user)
    hint = f"_(осталось раскладов сегодня: {remaining})_\n\n" if not is_pro else ""
    await callback.message.edit_text(
        f"🔮 {hint}О чём хочешь спросить карты?\n\nНапиши свой вопрос — или просто то, что сейчас на душе.",
        parse_mode="Markdown",
        reply_markup=cancel_button()
    )


@router.message(TarotFSM.waiting_question_3)
async def tarot_3_interpret(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    question = message.text.strip()

    # NOTE: small concurrency window between check and increment exists here;
    # acceptable for MVP. Fix later with Redis lock per user.
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, message.from_user.id)
        can = await limit_service.can_do_tarot(session, user)

    if not can:
        await message.answer(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
        return

    await bot.send_chat_action(message.chat.id, "typing")
    cards = card_engine.draw(3)
    name = user.name or message.from_user.first_name or "незнакомка"

    interpretation = await claude_service.interpret_tarot_3(cards, question, name)

    header = f"_{cards_line(cards)}_\n\n"
    text = header + interpretation

    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, message.from_user.id)
        await limit_service.use_tarot(session, user)

    await message.answer(text, parse_mode="Markdown", reply_markup=back_to_menu())


@router.callback_query(F.data == "tarot_relations")
async def tarot_relations_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, callback.from_user.id)
        can = await limit_service.can_do_tarot(session, user)

    if not can:
        await callback.message.edit_text(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
        return

    await state.set_state(TarotFSM.waiting_question_relations)
    await callback.message.edit_text(
        "💞 Расклад на отношения — 5 карт.\n\nО ком или о чём хочешь спросить?",
        reply_markup=cancel_button()
    )


@router.message(TarotFSM.waiting_question_relations)
async def tarot_relations_interpret(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    question = message.text.strip()

    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, message.from_user.id)
        can = await limit_service.can_do_tarot(session, user)

    if not can:
        await message.answer(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
        return

    await bot.send_chat_action(message.chat.id, "typing")
    cards = card_engine.draw(5)
    name = user.name or message.from_user.first_name or "незнакомка"

    interpretation = await claude_service.interpret_relationship_5(cards, question, name)

    header = f"_{cards_line(cards)}_\n\n"
    text = header + interpretation

    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, message.from_user.id)
        await limit_service.use_tarot(session, user)

    await message.answer(text, parse_mode="Markdown", reply_markup=back_to_menu())


@router.callback_query(F.data == "tarot_year")
async def tarot_year(callback: CallbackQuery, bot: Bot) -> None:
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, callback.from_user.id)

    if not limit_service.is_pro_active(user):
        await callback.message.edit_text(
            "📅 Расклад на год доступен только в Pro-подписке.\n\n"
            "Это глубокая работа — 12 карт, каждая открывает свой месяц...",
            parse_mode="Markdown",
            reply_markup=paywall_menu()
        )
        return

    await bot.send_chat_action(callback.message.chat.id, "typing")
    cards = card_engine.draw(12)
    name = user.name or callback.from_user.first_name or "незнакомка"
    zodiac = user.zodiac_sign or "неизвестный знак"

    interpretation = await claude_service.yearly_forecast_12(name, zodiac, cards)
    await callback.message.edit_text(interpretation, parse_mode="Markdown", reply_markup=back_to_menu())
