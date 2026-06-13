from datetime import date, datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.db import crud
from bot.db.models import User


def _today_msk() -> date:
    msk = timezone(timedelta(hours=3))
    return datetime.now(msk).date()


def is_pro_active(user: User) -> bool:
    """Returns True only if subscription exists AND has not expired."""
    if not user.is_pro:
        return False
    if user.pro_until is None:
        return False
    pro_until = user.pro_until
    # SQLite (dev) returns naive datetimes; Postgres returns aware. Normalise
    # to UTC-aware so the comparison never raises naive/aware TypeError.
    if pro_until.tzinfo is None:
        pro_until = pro_until.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < pro_until


async def can_do_tarot(session: AsyncSession, user: User) -> bool:
    if is_pro_active(user):
        return True
    if user.extra_spreads > 0:
        return True
    today = _today_msk()
    limit = await crud.get_daily_limit(session, user.telegram_id, today)
    return limit.tarot_count < settings.FREE_SPREADS_PER_DAY


async def can_do_horoscope(session: AsyncSession, user: User) -> bool:
    if is_pro_active(user):
        return True
    today = _today_msk()
    limit = await crud.get_daily_limit(session, user.telegram_id, today)
    return limit.horoscope_count < 1


async def use_tarot(session: AsyncSession, user: User) -> None:
    if is_pro_active(user):
        return
    if user.extra_spreads > 0:
        await crud.use_extra_spread(session, user.telegram_id)
        return
    today = _today_msk()
    await crud.increment_tarot(session, user.telegram_id, today)


async def use_horoscope(session: AsyncSession, user_id: int) -> None:
    today = _today_msk()
    await crud.increment_horoscope(session, user_id, today)


async def remaining_tarot(session: AsyncSession, user: User) -> int:
    if is_pro_active(user):
        return 999
    if user.extra_spreads > 0:
        return user.extra_spreads
    today = _today_msk()
    limit = await crud.get_daily_limit(session, user.telegram_id, today)
    return max(0, settings.FREE_SPREADS_PER_DAY - limit.tarot_count)
