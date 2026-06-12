import re
from datetime import date
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.db.session import async_session_factory
from bot.db import crud
from bot.keyboards.inline import main_menu, zodiac_keyboard, cancel_button, persona_keyboard
from bot.services.limit_service import is_pro_active
from bot.utils.text_utils import ZODIAC_EMOJI

_VALID_PERSONAS = {"young_moon", "full_moon", "dark_moon"}

router = Router()

_DATE_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$")

# Sentinel year for users who gave only day+month.
# Must be a LEAP year so 29.02 birthdays are accepted (1900 is not).
_NO_YEAR = 2000


class OnboardingFSM(StatesGroup):
    # Triggered voluntarily (profile setup) or after first spread
    waiting_persona = State()
    waiting_name = State()
    waiting_zodiac = State()
    waiting_birth_date = State()


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
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, callback.from_user.id)

    await state.set_state(OnboardingFSM.waiting_persona)
    await callback.message.edit_text(
        "🌙 Сначала — кто будет говорить с тобой?\n\n"
        "У Луны три лица. Выбери своё.",
        reply_markup=persona_keyboard(is_pro=is_pro_active(user), prefix="onb_persona")
    )


@router.callback_query(OnboardingFSM.waiting_persona, F.data.startswith("onb_persona:"))
async def onboarding_persona(callback: CallbackQuery, state: FSMContext) -> None:
    persona = callback.data.split(":", 1)[1]
    if persona not in _VALID_PERSONAS:
        await callback.answer("Выбери Луну с клавиатуры.", show_alert=True)
        return

    await state.update_data(persona=persona)
    await state.set_state(OnboardingFSM.waiting_name)
    await callback.message.edit_text(
        "🌙 Как тебя зовут?",
        reply_markup=cancel_button()
    )


@router.message(OnboardingFSM.waiting_name, F.text)
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
    # callback.data is client-supplied — whitelist against known signs
    if zodiac not in ZODIAC_EMOJI:
        await callback.answer("Выбери знак с клавиатуры.", show_alert=True)
        return
    await state.update_data(zodiac=zodiac)
    await state.set_state(OnboardingFSM.waiting_birth_date)
    await callback.message.edit_text(
        f"*{zodiac}*... Красиво.\n\n"
        "Когда ты родилась?\n\n"
        "_Напиши дату в формате ДД.ММ или ДД.ММ.ГГГГ_\n"
        "_Например: 15.03 или 15.03.1995_",
        parse_mode="Markdown",
        reply_markup=_skip_birthdate_keyboard()
    )


def _skip_birthdate_keyboard():
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Пропустить →", callback_data="skip_birthdate"))
    return builder.as_markup()


@router.callback_query(OnboardingFSM.waiting_birth_date, F.data == "skip_birthdate")
async def skip_birthdate(callback: CallbackQuery, state: FSMContext) -> None:
    await _finish_onboarding(callback, state, birth_date=None)


@router.message(OnboardingFSM.waiting_birth_date, F.text)
async def process_birth_date(message: Message, state: FSMContext) -> None:
    m = _DATE_RE.match(message.text.strip())
    if not m:
        await message.answer(
            "🌙 Не могу прочитать дату.\n"
            "Напиши в формате ДД.ММ или ДД.ММ.ГГГГ, например: _15.03_",
            parse_mode="Markdown",
            reply_markup=_skip_birthdate_keyboard()
        )
        return

    day, month = int(m.group(1)), int(m.group(2))
    year = int(m.group(3)) if m.group(3) else _NO_YEAR
    try:
        birth_date = date(year, month, day)
    except ValueError:
        await message.answer(
            "🌙 Такой даты не существует. Попробуй ещё раз.",
            reply_markup=_skip_birthdate_keyboard()
        )
        return

    await _finish_onboarding_message(message, state, birth_date=birth_date)


async def _finish_onboarding(callback: CallbackQuery, state: FSMContext, birth_date) -> None:
    data = await state.get_data()
    name = data.get("name", callback.from_user.first_name or "незнакомка")
    zodiac = data.get("zodiac", "")
    extra = {}
    if birth_date:
        extra["birth_date"] = birth_date
    if data.get("persona") in _VALID_PERSONAS:
        extra["luna_persona"] = data["persona"]
    async with async_session_factory() as session:
        await crud.update_user(
            session, callback.from_user.id,
            name=name, zodiac_sign=zodiac, **extra
        )
    await state.clear()
    await callback.message.edit_text(
        f"Я запомнила, {name}.\n\nЧто хочешь узнать сегодня?",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


async def _finish_onboarding_message(message: Message, state: FSMContext, birth_date) -> None:
    data = await state.get_data()
    name = data.get("name", message.from_user.first_name or "незнакомка")
    zodiac = data.get("zodiac", "")
    extra = {}
    if birth_date:
        extra["birth_date"] = birth_date
    if data.get("persona") in _VALID_PERSONAS:
        extra["luna_persona"] = data["persona"]
    async with async_session_factory() as session:
        await crud.update_user(
            session, message.from_user.id,
            name=name, zodiac_sign=zodiac, **extra
        )
    await state.clear()
    await message.answer(
        f"Я запомнила, {name}.\n\nЧто хочешь узнать сегодня?",
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
