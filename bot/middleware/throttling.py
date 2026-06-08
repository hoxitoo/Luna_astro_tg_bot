"""Anti-flood middleware: max 1 message per second per user via Redis NX key."""
import logging
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)

THROTTLE_SECONDS = 1.0
THROTTLE_TEXT = "🌙 Подожди немного..."


class ThrottlingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        user = data.get("event_from_user")
        if user:
            from bot.services.cache_service import set_user_flag
            allowed = await set_user_flag(user.id, "throttle", ttl=1)
            if not allowed:
                if isinstance(event, CallbackQuery):
                    await event.answer(THROTTLE_TEXT)
                elif isinstance(event, Message):
                    await event.answer(THROTTLE_TEXT)
                return None
        return await handler(event, data)
