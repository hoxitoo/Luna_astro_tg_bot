"""Scheduled jobs: card-of-day, moon phases, Mercury retrograde, subscription reminders."""
import asyncio
import logging
from datetime import date, datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select

from bot.db.session import async_session_factory
from bot.db.models import User
from bot.db import crud
from bot.services.card_engine import card_engine
from bot.services import claude_service
from bot.services.cache_service import get_redis
from bot.utils.text_utils import card_display_name

logger = logging.getLogger(__name__)
MSK = timezone(timedelta(hours=3))

# Telegram limits: 30 msg/sec global, 1 msg/sec per user
# 0.05 s delay ≈ 20 msg/sec — safe margin
_BROADCAST_DELAY = 0.05

# ---------------------------------------------------------------------------
# Hardcoded astro calendar 2025–2026
# ---------------------------------------------------------------------------

# (date, is_full_moon) — False = new moon, True = full moon
_MOON_EVENTS: list[tuple[date, bool]] = [
    # 2025
    (date(2025, 1, 13), True),  (date(2025, 1, 29), False),
    (date(2025, 2, 12), True),  (date(2025, 2, 28), False),
    (date(2025, 3, 14), True),  (date(2025, 3, 29), False),
    (date(2025, 4, 13), True),  (date(2025, 4, 27), False),
    (date(2025, 5, 12), True),  (date(2025, 5, 27), False),
    (date(2025, 6, 11), True),  (date(2025, 6, 25), False),
    (date(2025, 7, 10), True),  (date(2025, 7, 24), False),
    (date(2025, 8, 9),  True),  (date(2025, 8, 23), False),
    (date(2025, 9, 7),  True),  (date(2025, 9, 21), False),
    (date(2025, 10, 7), True),  (date(2025, 10, 21), False),
    (date(2025, 11, 5), True),  (date(2025, 11, 20), False),
    (date(2025, 12, 4), True),  (date(2025, 12, 19), False),
    # 2026
    (date(2026, 1, 3),  True),  (date(2026, 1, 18), False),
    (date(2026, 2, 1),  True),  (date(2026, 2, 17), False),
    (date(2026, 3, 3),  True),  (date(2026, 3, 18), False),
    (date(2026, 4, 2),  True),  (date(2026, 4, 17), False),
    (date(2026, 5, 1),  True),  (date(2026, 5, 16), False),
    (date(2026, 5, 31), True),  (date(2026, 6, 15), False),
    (date(2026, 6, 29), True),  (date(2026, 7, 14), False),
    (date(2026, 7, 29), True),  (date(2026, 8, 12), False),
    (date(2026, 8, 27), True),  (date(2026, 9, 11), False),
    (date(2026, 9, 26), True),  (date(2026, 10, 10), False),
    (date(2026, 10, 25), True), (date(2026, 11, 9), False),
    (date(2026, 11, 24), True), (date(2026, 12, 8), False),
    (date(2026, 12, 23), True),
]

# Dates when Mercury retrograde STARTS — send a warning push that morning
_MERCURY_RETROGRADE_STARTS: list[date] = [
    date(2025, 3, 15),
    date(2025, 7, 18),
    date(2025, 11, 9),
    date(2026, 2, 25),
    date(2026, 6, 29),
    date(2026, 10, 15),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_all_user_ids() -> list[int]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.is_active.is_(True))
        )
        return result.scalars().all()


async def _mark_blocked(user_ids: list[int]) -> None:
    """Mark users who blocked the bot so future broadcasts skip them."""
    if not user_ids:
        return
    async with async_session_factory() as session:
        await crud.mark_users_inactive(session, user_ids)
    logger.info(f"Marked {len(user_ids)} users inactive (blocked the bot)")


async def _broadcast(bot: Bot, text: str, lock_key: str) -> tuple[int, int]:
    """Send message to all active users with flood-control delay.

    Uses Redis distributed lock to prevent duplicate sends (e.g. on restart).
    Returns (sent_count, failed_count).
    """
    redis = get_redis()
    acquired = await redis.set(lock_key, 1, ex=3600 * 12, nx=True)
    if not acquired:
        logger.info(f"Broadcast '{lock_key}' already sent, skipping.")
        return 0, 0

    user_ids = await _get_all_user_ids()
    sent = failed = 0
    blocked: list[int] = []
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="Markdown")
            sent += 1
        except TelegramForbiddenError:
            blocked.append(uid)
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(_BROADCAST_DELAY)

    await _mark_blocked(blocked)
    logger.info(f"Broadcast '{lock_key}': sent={sent}, failed={failed}")
    return sent, failed

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

async def _broadcast_card_of_day(bot: Bot) -> None:
    today = datetime.now(MSK).strftime("%Y-%m-%d")
    card = card_engine.draw(1)[0]
    today_fmt = datetime.now(MSK).strftime("%d %B %Y")
    try:
        text_body = await claude_service.card_of_day(card, today_fmt)
    except claude_service.ClaudeUnavailable:
        text_body = claude_service.get_fallback("card_of_day")
    text = f"🃏 *{card_display_name(card)}*\n\n{text_body}"
    await _broadcast(bot, text, f"broadcast:card_of_day:{today}")


async def _check_moon_events(bot: Bot) -> None:
    today = datetime.now(MSK).date()
    event = next((e for e in _MOON_EVENTS if e[0] == today), None)
    if not event:
        return

    _, is_full = event
    if is_full:
        text = (
            "🌕 *Сегодня полнолуние.*\n\n"
            "Это время завершений, отпускания и ясности.\n"
            "Что стало очевидным за этот лунный цикл?\n\n"
            "Карты сегодня особенно красноречивы. 🌙"
        )
        lock_key = f"broadcast:full_moon:{today}"
    else:
        text = (
            "🌑 *Сегодня новолуние.*\n\n"
            "Время намерений, новых начал и посева.\n"
            "Что ты хочешь призвать в этом цикле?\n\n"
            "Карты помогут найти направление. 🌙"
        )
        lock_key = f"broadcast:new_moon:{today}"

    await _broadcast(bot, text, lock_key)


async def _check_mercury_retrograde(bot: Bot) -> None:
    today = datetime.now(MSK).date()
    if today not in _MERCURY_RETROGRADE_STARTS:
        return

    text = (
        "☿ *Сегодня Меркурий входит в ретроградность.*\n\n"
        "Это период переосмыслений. Техника барахлит, слова теряются, "
        "прошлое возвращается.\n\n"
        "Не подписывай важных договоров. Не принимай поспешных решений.\n"
        "Зато — отличное время разобраться в том, что давно откладывалось.\n\n"
        "Что говорят карты об этом периоде для тебя? 🌙"
    )
    await _broadcast(bot, text, f"broadcast:mercury_rx:{today}")


async def _send_birthday_spreads(bot: Bot) -> None:
    """Send a personal Solar Return spread to each user whose birthday is today (MSK)."""
    today = datetime.now(MSK).strftime("%Y-%m-%d")
    # Same distributed lock as other broadcasts — a birthday message must never duplicate
    redis = get_redis()
    acquired = await redis.set(f"broadcast:birthday:{today}", 1, ex=3600 * 12, nx=True)
    if not acquired:
        logger.info("Birthday spreads already sent today, skipping.")
        return

    async with async_session_factory() as session:
        users = await crud.get_users_with_birthday_today(session)

    if not users:
        return

    sent = failed = 0
    blocked: list[int] = []
    for user in users:
        try:
            cards = card_engine.draw(3)
            name = user.name or "незнакомка"
            zodiac = user.zodiac_sign or "неизвестный знак"
            text = await claude_service.birthday_solar_return(
                name, zodiac, cards, persona=user.luna_persona
            )
            cards_header = " · ".join(c["name_ru"] for c in cards)
            await bot.send_message(
                user.telegram_id,
                f"🎂 *{cards_header}*\n\n{text}",
                parse_mode="Markdown"
            )
            async with async_session_factory() as session:
                await crud.save_spread(
                    session, user.telegram_id, "birthday", text,
                    cards_json=cards
                )
            sent += 1
        except TelegramForbiddenError:
            blocked.append(user.telegram_id)
            failed += 1
        except Exception as e:
            # incl. ClaudeUnavailable — a canned birthday message is worse than none
            logger.warning(f"Birthday spread failed for {user.telegram_id}: {e}")
            failed += 1
        await asyncio.sleep(_BROADCAST_DELAY)

    await _mark_blocked(blocked)
    logger.info(f"Birthday spreads: sent={sent}, failed={failed}")


async def _check_subscription_expiry(bot: Bot) -> None:
    """Remind users whose Pro subscription expires in exactly 3 days."""
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(days=3)
    window_end = window_start + timedelta(hours=24)

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(
                User.is_pro.is_(True),
                User.pro_until >= window_start,
                User.pro_until < window_end,
            )
        )
        expiring_users = result.scalars().all()

    if not expiring_users:
        return

    text = (
        "🌙 Через 3 дня заканчивается твоя Pro-подписка.\n\n"
        "Продли её, чтобы не терять безлимитные расклады "
        "и ежедневный гороскоп.\n\n"
        "Нажми /start → 💎 Pro-подписка"
    )

    sent = failed = 0
    blocked: list[int] = []
    for user in expiring_users:
        try:
            await bot.send_message(user.telegram_id, text)
            sent += 1
        except TelegramForbiddenError:
            blocked.append(user.telegram_id)
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(_BROADCAST_DELAY)

    await _mark_blocked(blocked)
    logger.info(f"Subscription expiry reminders: sent={sent}, failed={failed}")


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------

def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    # Card of day — 09:00 MSK every day
    scheduler.add_job(
        _broadcast_card_of_day,
        trigger=CronTrigger(hour=9, minute=0),
        args=[bot], id="card_of_day", replace_existing=True,
    )
    # Moon phases — 10:00 MSK (separate from card of day)
    scheduler.add_job(
        _check_moon_events,
        trigger=CronTrigger(hour=10, minute=0),
        args=[bot], id="moon_events", replace_existing=True,
    )
    # Mercury retrograde — 10:05 MSK
    scheduler.add_job(
        _check_mercury_retrograde,
        trigger=CronTrigger(hour=10, minute=5),
        args=[bot], id="mercury_rx", replace_existing=True,
    )
    # Subscription expiry reminders — 12:00 MSK
    scheduler.add_job(
        _check_subscription_expiry,
        trigger=CronTrigger(hour=12, minute=0),
        args=[bot], id="sub_expiry", replace_existing=True,
    )
    # Birthday Solar Return spreads — 08:00 MSK
    scheduler.add_job(
        _send_birthday_spreads,
        trigger=CronTrigger(hour=8, minute=0),
        args=[bot], id="birthday_spreads", replace_existing=True,
    )

    return scheduler
