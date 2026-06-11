from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.db.session import async_session_factory
from bot.db import crud
from bot.keyboards.inline import main_menu, zodiac_keyboard, cancel_button

router = Router()


class OnboardingFSM(StatesGroup):
    # Triggered voluntarily (profile setup) or after first spread
    waiting_name = State()
    waiting_zodiac = State()


WELCOME_NEW = (
    "🌙 *Я — Луна.*\n\n"
    "Я читаю карты и слушаю звёзды.\n"
    "Три расклада в день — бесплатно.\n\n"
    "Что хочешь узнать сегодня?"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()

    # Parse referral code: /start ref_12345
    ref_id: int | None = None
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try:
            ref_id = int(parts[1][4:])
        except ValueError:
            pass

    async with async_session_factory() as session:
        user = await crud.get_or_create_user(
            session, message.from_user.id, message.from_user.username
        )
        # Apply referral bonus (7 days Pro to both) — only once, skip self-ref
        if ref_id and ref_id != message.from_user.id and not user.referred_by:
            await crud.apply_referral(session, user.telegram_id, ref_id)

    if user.name:
        text = f"🌙 С возвращением, {user.name}..."
    else:
        text = WELCOME_NEW

    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu())


# ---------------------------------------------------------------------------
# Voluntary profile setup — triggered by "setup_profile" callback
# or automatically after a user's first spread (see tarot.py)
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "setup_profile")
async def setup_profile(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OnboardingFSM.waiting_name)
    await callback.message.edit_text(
        "🌙 Как тебя зовут?",
        reply_markup=cancel_button()
    )


@router.message(OnboardingFSM.waiting_name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()[:64]
    await state.update_data(name=name)
    await state.set_state(OnboardingFSM.waiting_zodiac)
    await message.answer(
        f"*{name}*...\n\nЧто-то в этом имени есть.\n\nКакой у тебя знак зодиака?",
        parse_mode="Markdown",
        reply_markup=zodiac_keyboard()
    )


@router.callback_query(OnboardingFSM.waiting_zodiac, F.data.startswith("zodiac_"))
async def process_zodiac(callback: CallbackQuery, state: FSMContext) -> None:
    zodiac = callback.data.replace("zodiac_", "")
    data = await state.get_data()
    name = data.get("name", callback.from_user.first_name)

    async with async_session_factory() as session:
        await crud.update_user(
            session, callback.from_user.id,
            name=name, zodiac_sign=zodiac
        )

    await state.clear()
    await callback.message.edit_text(
        f"*{zodiac}*...\n\nЯ запомнила.\n\nЧто хочешь узнать сегодня, {name}?",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


@router.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🌙 Что хочешь узнать?",
        reply_markup=main_menu()
    )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🌙 Хорошо...",
        reply_markup=main_menu()
    )
