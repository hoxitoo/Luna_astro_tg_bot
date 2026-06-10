"""
Tests for crud.set_pro subscription renewal logic.
Uses a full async SQLite in-memory DB so no PostgreSQL needed.
"""
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
async def test_set_pro_new_user(session):
    """Fresh user gets Pro from now + 30 days."""
    before = datetime.now(timezone.utc)
    user = await crud.get_or_create_user(session, telegram_id=101)
    await crud.set_pro(session, 101, "month")

    result = await session.execute(select(User).where(User.telegram_id == 101))
    updated = result.scalar_one()
    after = datetime.now(timezone.utc)

    assert updated.is_pro is True
    assert updated.pro_until is not None
    expected_min = before + timedelta(days=30)
    expected_max = after + timedelta(days=30)
    assert expected_min <= updated.pro_until <= expected_max


@pytest.mark.asyncio
async def test_set_pro_year_plan(session):
    """Year plan gives 365 days."""
    user = await crud.get_or_create_user(session, telegram_id=102)
    before = datetime.now(timezone.utc)
    await crud.set_pro(session, 102, "year")

    result = await session.execute(select(User).where(User.telegram_id == 102))
    updated = result.scalar_one()
    after = datetime.now(timezone.utc)

    expected_min = before + timedelta(days=365)
    expected_max = after + timedelta(days=365)
    assert expected_min <= updated.pro_until <= expected_max


@pytest.mark.asyncio
async def test_set_pro_renewal_extends_from_current_expiry(session):
    """Renewing an active subscription extends from current expiry, not now."""
    user = await crud.get_or_create_user(session, telegram_id=103)
    future_expiry = datetime.now(timezone.utc) + timedelta(days=10)
    await crud.update_user(session, 103, is_pro=True, pro_until=future_expiry)

    await crud.set_pro(session, 103, "month")

    result = await session.execute(select(User).where(User.telegram_id == 103))
    updated = result.scalar_one()

    # Should be ~40 days from now (10 remaining + 30 new), not ~30
    expected_approx = future_expiry + timedelta(days=30)
    diff = abs((updated.pro_until - expected_approx).total_seconds())
    assert diff < 5, f"Expected ~40 days from now, got {updated.pro_until}"


@pytest.mark.asyncio
async def test_set_pro_expired_subscription_restarts_from_now(session):
    """Expired subscription starts fresh from now, not from past expiry."""
    user = await crud.get_or_create_user(session, telegram_id=104)
    past_expiry = datetime.now(timezone.utc) - timedelta(days=5)
    await crud.update_user(session, 104, is_pro=True, pro_until=past_expiry)

    before = datetime.now(timezone.utc)
    await crud.set_pro(session, 104, "month")
    after = datetime.now(timezone.utc)

    result = await session.execute(select(User).where(User.telegram_id == 104))
    updated = result.scalar_one()

    expected_min = before + timedelta(days=30)
    expected_max = after + timedelta(days=30)
    assert expected_min <= updated.pro_until <= expected_max
