"""Tests for referral system (crud.apply_referral)."""
import os
import pytest
import asyncio
from datetime import datetime, timezone, timedelta

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from bot.db.models import Base, User
from bot.db import crud


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s


@pytest.mark.asyncio
async def test_apply_referral_gives_pro_to_both(session):
    referrer = await crud.get_or_create_user(session, telegram_id=201)
    referred = await crud.get_or_create_user(session, telegram_id=202)

    result = await crud.apply_referral(session, referred.telegram_id, referrer.telegram_id)
    assert result is True

    # Both should now have Pro
    res_ref = await session.execute(select(User).where(User.telegram_id == 201))
    res_new = await session.execute(select(User).where(User.telegram_id == 202))
    referrer_updated = res_ref.scalar_one()
    referred_updated = res_new.scalar_one()

    assert referrer_updated.is_pro is True
    assert referred_updated.is_pro is True
    assert referred_updated.referred_by == 201
    assert referred_updated.referral_bonus_given is True


@pytest.mark.asyncio
async def test_apply_referral_pro_lasts_7_days(session):
    await crud.get_or_create_user(session, telegram_id=203)
    await crud.get_or_create_user(session, telegram_id=204)

    before = datetime.now(timezone.utc)
    await crud.apply_referral(session, 204, 203)
    after = datetime.now(timezone.utc)

    res = await session.execute(select(User).where(User.telegram_id == 204))
    user = res.scalar_one()

    # SQLite may return naive datetimes — strip tzinfo for comparison
    pro_until = user.pro_until.replace(tzinfo=None) if user.pro_until.tzinfo else user.pro_until
    expected_min = (before + timedelta(days=7)).replace(tzinfo=None)
    expected_max = (after + timedelta(days=7)).replace(tzinfo=None)
    assert expected_min <= pro_until <= expected_max


@pytest.mark.asyncio
async def test_apply_referral_cannot_be_applied_twice(session):
    await crud.get_or_create_user(session, telegram_id=205)
    await crud.get_or_create_user(session, telegram_id=206)

    first = await crud.apply_referral(session, 206, 205)
    second = await crud.apply_referral(session, 206, 205)

    assert first is True
    assert second is False  # Already has referred_by set


@pytest.mark.asyncio
async def test_apply_referral_sets_referred_by(session):
    await crud.get_or_create_user(session, telegram_id=207)
    await crud.get_or_create_user(session, telegram_id=208)

    await crud.apply_referral(session, 208, 207)

    res = await session.execute(select(User).where(User.telegram_id == 208))
    user = res.scalar_one()
    assert user.referred_by == 207
