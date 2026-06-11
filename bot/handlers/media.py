"""Handlers for non-text input: voice, photo, sticker, document, video."""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.keyboards.inline import main_menu

router = Router()

_VOICE_REPLY = (
    "🌙 Я слышу тебя... но пока не умею слушать голос.\n\n"
    "Напиши мне текстом — и я отвечу."
)

_MEDIA_REPLY = (
    "🌙 Я работаю со словами.\n\n"
    "Напиши мне свой вопрос текстом."
)

_STICKER_REPLIES = [
    "🌙 ...",
    "🌙 Что-то в тебе сейчас молчит.",
    "🌙 Иногда достаточно паузы.",
]

import random


@router.message(F.voice | F.audio)
async def handle_voice(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is not None:
        # Inside a conversation flow — ask to type the answer
        await message.answer(
            "🌙 Напиши ответ текстом — я жду."
        )
    else:
        await message.answer(_VOICE_REPLY, reply_markup=main_menu())


@router.message(F.photo | F.video | F.document | F.animation)
async def handle_photo(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is not None:
        await message.answer("🌙 Напиши текстом — я жду.")
    else:
        await message.answer(_MEDIA_REPLY, reply_markup=main_menu())


@router.message(F.sticker)
async def handle_sticker(message: Message) -> None:
    await message.answer(random.choice(_STICKER_REPLIES))
