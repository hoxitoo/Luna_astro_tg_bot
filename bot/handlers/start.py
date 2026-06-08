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
    waiting_name = State()
    waiting_zodiac = State()


WELCOME_TEXT = (
    "🌙 *Я — Луна.*\n\n"
    "Я читаю карты и слушаю звёзды.\n"
    "Каждый день — три бесплатных расклада.\n\n"
    "Как тебя зовут?"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    async with async_session_factory() as session:
        user = await crud.get_or_create_user(
            session, message.from_user.id, message.from_user.username
        )

    if user.name and user.zodiac_sign:
        await message.answer(
            f"🌙 С возвращением, {user.name}...",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
        return

    await state.set_state(OnboardingFSM.waiting_name)
    await message.answer(WELCOME_TEXT, parse_mode="Markdown", reply_markup=cancel_button())


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
