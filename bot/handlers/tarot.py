from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services import limit_service, claude_service
from bot.services.card_engine import card_engine
from bot.services.cache_service import set_user_flag, clear_user_flag
from bot.keyboards.inline import cancel_button, back_to_menu, tarot_menu, paywall_menu
from bot.utils.text_utils import cards_line, truncate, validate_question

router = Router()

BUSY_TEXT = "🌙 Я ещё раскладываю карты... подожди немного."

FALLBACK_NOTE = "\n\n_Звёзды сейчас молчат — этот расклад не считается._"

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
    waiting_past_situation = State()


def _after_spread_keyboard(show_name_prompt: bool) -> object:
    """Back-to-menu keyboard, with optional 'tell me your name' button."""
    builder = InlineKeyboardBuilder()
    if show_name_prompt:
        builder.row(InlineKeyboardButton(
            text="📝 Назвать своё имя",
            callback_data="setup_profile"
        ))
    builder.row(InlineKeyboardButton(text="◀️ В главное меню", callback_data="main_menu"))
    return builder.as_markup()


async def _answer_md_safe(message: Message, text: str, reply_markup=None) -> None:
    """Send with Markdown; if Claude emitted unbalanced markup, resend as plain text."""
    try:
        await message.answer(text, parse_mode="Markdown", reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text, parse_mode=None, reply_markup=reply_markup)


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
        f"🔮 {hint}О чём хочешь спросить карты?\n\n"
        "Напиши свой вопрос — или просто то, что сейчас на душе.",
        parse_mode="Markdown",
        reply_markup=cancel_button()
    )


@router.message(TarotFSM.waiting_question_3, F.text)
async def tarot_3_interpret(message: Message, state: FSMContext, bot: Bot) -> None:
    question = message.text.strip()

    # Validate question length
    if err := validate_question(question):
        await message.answer(err, reply_markup=cancel_button())
        # Keep FSM state active — user can try again
        await state.set_state(TarotFSM.waiting_question_3)
        return

    await state.clear()

    # Per-user lock closes the check→increment race (3 concurrent spreads on 1 remaining)
    if not await set_user_flag(message.from_user.id, "spread_lock", ttl=60):
        await message.answer(BUSY_TEXT)
        return

    try:
        async with async_session_factory() as session:
            user = await crud.get_or_create_user(session, message.from_user.id)
            can = await limit_service.can_do_tarot(session, user)

        if not can:
            await message.answer(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
            return

        await bot.send_chat_action(message.chat.id, "typing")
        cards = card_engine.draw(3)
        name = user.name or message.from_user.first_name or "незнакомка"

        try:
            interpretation = await claude_service.interpret_tarot_3(
                cards, question, name, persona=user.luna_persona
            )
        except claude_service.ClaudeUnavailable:
            # Don't charge the limit, don't archive the canned text
            await _answer_md_safe(
                message,
                claude_service.get_fallback("tarot") + FALLBACK_NOTE,
                reply_markup=back_to_menu(),
            )
            return

        text = f"_{cards_line(cards)}_\n\n{interpretation}"

        async with async_session_factory() as session:
            user = await crud.get_or_create_user(session, message.from_user.id)
            await limit_service.use_tarot(session, user)
            await crud.save_spread(
                session, user.telegram_id, "tarot_3", interpretation,
                question=question, cards_json=cards
            )

        # Show "tell me your name" prompt for anonymous users after their first spread
        await _answer_md_safe(
            message, text,
            reply_markup=_after_spread_keyboard(show_name_prompt=not user.name)
        )
    finally:
        await clear_user_flag(message.from_user.id, "spread_lock")


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


@router.message(TarotFSM.waiting_question_relations, F.text)
async def tarot_relations_interpret(message: Message, state: FSMContext, bot: Bot) -> None:
    question = message.text.strip()

    if err := validate_question(question):
        await message.answer(err, reply_markup=cancel_button())
        await state.set_state(TarotFSM.waiting_question_relations)
        return

    await state.clear()

    if not await set_user_flag(message.from_user.id, "spread_lock", ttl=60):
        await message.answer(BUSY_TEXT)
        return

    try:
        async with async_session_factory() as session:
            user = await crud.get_or_create_user(session, message.from_user.id)
            can = await limit_service.can_do_tarot(session, user)

        if not can:
            await message.answer(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
            return

        await bot.send_chat_action(message.chat.id, "typing")
        cards = card_engine.draw(5)
        name = user.name or message.from_user.first_name or "незнакомка"

        try:
            interpretation = await claude_service.interpret_relationship_5(
                cards, question, name, persona=user.luna_persona
            )
        except claude_service.ClaudeUnavailable:
            await _answer_md_safe(
                message,
                claude_service.get_fallback("tarot") + FALLBACK_NOTE,
                reply_markup=back_to_menu(),
            )
            return

        text = f"_{cards_line(cards)}_\n\n{interpretation}"

        async with async_session_factory() as session:
            user = await crud.get_or_create_user(session, message.from_user.id)
            await limit_service.use_tarot(session, user)
            await crud.save_spread(
                session, user.telegram_id, "relations_5", interpretation,
                question=question, cards_json=cards
            )

        await _answer_md_safe(
            message, text,
            reply_markup=_after_spread_keyboard(show_name_prompt=not user.name)
        )
    finally:
        await clear_user_flag(message.from_user.id, "spread_lock")


@router.callback_query(F.data == "tarot_past")
async def tarot_past_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, callback.from_user.id)
        can = await limit_service.can_do_tarot(session, user)

    if not can:
        await callback.message.edit_text(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
        return

    await state.set_state(TarotFSM.waiting_past_situation)
    await callback.message.edit_text(
        "🌑 *Расклад на прошлое.*\n\n"
        "Опиши ситуацию, которая уже произошла.\n"
        "Что это было — и чем закончилось?\n\n"
        "_Можно коротко. Главное — честно._",
        parse_mode="Markdown",
        reply_markup=cancel_button()
    )


@router.message(TarotFSM.waiting_past_situation, F.text)
async def tarot_past_interpret(message: Message, state: FSMContext, bot: Bot) -> None:
    situation = message.text.strip()

    if err := validate_question(situation):
        await message.answer(err, reply_markup=cancel_button())
        await state.set_state(TarotFSM.waiting_past_situation)
        return

    await state.clear()

    if not await set_user_flag(message.from_user.id, "spread_lock", ttl=60):
        await message.answer(BUSY_TEXT)
        return

    try:
        async with async_session_factory() as session:
            user = await crud.get_or_create_user(session, message.from_user.id)
            can = await limit_service.can_do_tarot(session, user)

        if not can:
            await message.answer(PAYWALL_TEXT, parse_mode="Markdown", reply_markup=paywall_menu())
            return

        await bot.send_chat_action(message.chat.id, "typing")
        cards = card_engine.draw(3)
        name = user.name or message.from_user.first_name or "незнакомка"

        try:
            interpretation = await claude_service.interpret_past_spread(
                cards, situation, name, persona=user.luna_persona
            )
        except claude_service.ClaudeUnavailable:
            await _answer_md_safe(
                message,
                claude_service.get_fallback("tarot") + FALLBACK_NOTE,
                reply_markup=back_to_menu(),
            )
            return

        text = f"_{cards_line(cards)}_\n\n{interpretation}"

        async with async_session_factory() as session:
            user = await crud.get_or_create_user(session, message.from_user.id)
            await limit_service.use_tarot(session, user)
            await crud.save_spread(
                session, user.telegram_id, "past", interpretation,
                question=situation, cards_json=cards
            )

        await _answer_md_safe(
            message, text,
            reply_markup=_after_spread_keyboard(show_name_prompt=not user.name)
        )
    finally:
        await clear_user_flag(message.from_user.id, "spread_lock")


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

    try:
        interpretation = await claude_service.yearly_forecast_12(
            name, zodiac, cards, persona=user.luna_persona
        )
    except claude_service.ClaudeUnavailable:
        await callback.message.edit_text(
            claude_service.get_fallback("tarot") + FALLBACK_NOTE,
            parse_mode="Markdown",
            reply_markup=back_to_menu()
        )
        return

    async with async_session_factory() as session:
        await crud.save_spread(
            session, user.telegram_id, "year_12", interpretation, cards_json=cards
        )
    # Yearly forecast can be 400+ words — guard against Telegram's 4096 char limit
    try:
        await callback.message.edit_text(
            truncate(interpretation, max_len=4096),
            parse_mode="Markdown",
            reply_markup=back_to_menu()
        )
    except TelegramBadRequest:
        await callback.message.edit_text(
            truncate(interpretation, max_len=4096),
            parse_mode=None,
            reply_markup=back_to_menu()
        )
