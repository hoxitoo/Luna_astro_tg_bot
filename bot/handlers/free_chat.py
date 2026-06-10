from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services import claude_service
from bot.keyboards.inline import main_menu

router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, state: FSMContext, bot: Bot) -> None:
    current_state = await state.get_state()
    if current_state is not None:
        return

    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, message.from_user.id)

    await bot.send_chat_action(message.chat.id, "typing")
    name = user.name or message.from_user.first_name or "незнакомка"
    response = await claude_service.free_chat(name, message.text.strip())
    await message.answer(response, parse_mode="Markdown", reply_markup=main_menu())
