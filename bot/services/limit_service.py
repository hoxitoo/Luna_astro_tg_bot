from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.db import crud


def _today_msk() -> "date":
    from datetime import date
    msk = timezone(timedelta(hours=3))
    return datetime.now(msk).date()


async def can_do_tarot(session: AsyncSession, user_id: int, is_pro: bool) -> bool:
    if is_pro:
        return True
    today = _today_msk()
    limit = await crud.get_daily_limit(session, user_id, today)
    return limit.tarot_count < settings.FREE_SPREADS_PER_DAY


async def can_do_horoscope(session: AsyncSession, user_id: int, is_pro: bool) -> bool:
    if is_pro:
        return True
    today = _today_msk()
    limit = await crud.get_daily_limit(session, user_id, today)
    return limit.horoscope_count < 1


async def use_tarot(session: AsyncSession, user_id: int) -> None:
    today = _today_msk()
    await crud.increment_tarot(session, user_id, today)


async def use_horoscope(session: AsyncSession, user_id: int) -> None:
    today = _today_msk()
    await crud.increment_horoscope(session, user_id, today)


async def remaining_tarot(session: AsyncSession, user_id: int) -> int:
    today = _today_msk()
    limit = await crud.get_daily_limit(session, user_id, today)
    return max(0, settings.FREE_SPREADS_PER_DAY - limit.tarot_count)
