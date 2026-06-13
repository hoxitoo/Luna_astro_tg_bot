import logging
import random
from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)
router = Router()

# Luna-voiced messages for unexpected technical hiccups — never break character.
_ERROR_LINES = [
    "🌙 Луна на мгновение скрылась за облаком...\n\n"
    "Это просто пауза. Попробуй ещё раз — или вернись в начало через /start.",
    "🌙 Связь на миг прервалась...\n\n"
    "Луна никуда не уходит. Повтори свой шаг чуть позже или начни заново — /start.",
    "🌙 Сейчас что-то мешает мне ответить в полный голос.\n\n"
    "Подожди мгновение и попробуй снова. Если нужно — вернись в главное меню через /start.",
]

# Short version for callback toasts (must be brief).
_ERROR_TOAST = "🌙 Луна на миг скрылась за облаком. Попробуй ещё раз."


@router.errors()
async def global_error_handler(event: ErrorEvent) -> None:
    logger.exception(f"Unhandled error on update {event.update.update_id}: {event.exception}")

    update = event.update
    message = None

    if update.message:
        message = update.message
    elif update.callback_query:
        try:
            await update.callback_query.answer(_ERROR_TOAST, show_alert=True)
        except Exception:
            pass
        message = update.callback_query.message

    if message:
        try:
            await message.answer(random.choice(_ERROR_LINES))
        except Exception:
            pass
