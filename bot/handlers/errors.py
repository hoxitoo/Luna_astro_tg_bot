import logging
from aiogram import Router
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)
router = Router()


@router.errors()
async def global_error_handler(event: ErrorEvent) -> None:
    logger.exception(f"Unhandled error on update {event.update.update_id}: {event.exception}")

    # Try to notify the user
    update = event.update
    message = None

    if update.message:
        message = update.message
    elif update.callback_query:
        try:
            await update.callback_query.answer("Что-то пошло не так. Попробуй ещё раз.", show_alert=True)
        except Exception:
            pass
        message = update.callback_query.message

    if message:
        try:
            await message.answer(
                "🌙 Что-то пошло не так...\n\nПопробуй ещё раз или вернись в главное меню — /start"
            )
        except Exception:
            pass
