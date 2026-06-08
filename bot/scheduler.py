"""Daily card-of-day broadcast at 09:00 MSK.
Uses APScheduler + Redis to avoid duplicate sends on restart.
"""
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from sqlalchemy import select
from bot.db.session import async_session_factory
from bot.db.models import User
from bot.services.card_engine import card_engine
from bot.services import claude_service
from bot.services.cache_service import get_redis

logger = logging.getLogger(__name__)
MSK = timezone(timedelta(hours=3))


async def _broadcast_card_of_day(bot: Bot) -> None:
    today = datetime.now(MSK).strftime("%Y-%m-%d")
    lock_key = f"broadcast:card_of_day:{today}"

    redis = get_redis()
    acquired = await redis.set(lock_key, 1, ex=3600 * 12, nx=True)
    if not acquired:
        logger.info("Card-of-day broadcast already sent today, skipping.")
        return

    card = card_engine.draw(1)[0]
    today_fmt = datetime.now(MSK).strftime("%d %B %Y")
    text_body = await claude_service.card_of_day(card, today_fmt)
    card_header = f"🃏 *{card['name_ru']}*{'  ↓' if card['reversed'] else ''}\n\n"
    text = card_header + text_body

    async with async_session_factory() as session:
        result = await session.execute(select(User.telegram_id))
        user_ids = result.scalars().all()

    sent = failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1

    logger.info(f"Card-of-day broadcast: sent={sent}, failed={failed}")


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        _broadcast_card_of_day,
        trigger=CronTrigger(hour=9, minute=0),
        args=[bot],
        id="card_of_day",
        replace_existing=True,
    )
    return scheduler
