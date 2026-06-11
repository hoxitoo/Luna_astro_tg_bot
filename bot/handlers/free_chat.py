from datetime import datetime, timezone, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.config import settings
from bot.db.session import async_session_factory
from bot.db import crud
from bot.services import claude_service
from bot.services.limit_service import is_pro_active
from bot.services.cache_service import get_daily_count, incr_daily_count
from bot.keyboards.inline import main_menu, paywall_menu

router = Router()

_CHAT_LIMIT_TEXT = (
    "🌙 Луна сегодня наговорилась...\n\n"
    "Слова — это поверхность. Карты видят глубже.\n"
    "Сделай расклад — или возвращайся завтра.\n\n"
    "_В Pro-подписке Луна разговаривает без ограничений._"
)


def _today_msk() -> str:
    msk = timezone(timedelta(hours=3))
    return datetime.now(msk).strftime("%Y-%m-%d")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, state: FSMContext, bot: Bot) -> None:
    current_state = await state.get_state()
    if current_state is not None:
        return

    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, message.from_user.id)

    # Free chat hits Claude on every message — cap it for free users,
    # otherwise one chatty user burns unbounded API spend
    pro = is_pro_active(user)
    today = _today_msk()
    if not pro:
        count = await get_daily_count(user.telegram_id, "chat", today)
        if count >= settings.FREE_CHAT_PER_DAY:
            await message.answer(
                _CHAT_LIMIT_TEXT, parse_mode="Markdown", reply_markup=paywall_menu()
            )
            return

    await bot.send_chat_action(message.chat.id, "typing")
    name = user.name or message.from_user.first_name or "незнакомка"
    try:
        response = await claude_service.free_chat(
            name, message.text.strip(), persona=user.luna_persona
        )
    except claude_service.ClaudeUnavailable:
        # Fallback shown for free — don't count it against the daily quota
        await message.answer(
            claude_service.get_fallback("free_chat"), reply_markup=main_menu()
        )
        return

    if not pro:
        await incr_daily_count(user.telegram_id, "chat", today)
    await message.answer(response, parse_mode="Markdown", reply_markup=main_menu())
