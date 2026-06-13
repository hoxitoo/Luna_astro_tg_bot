"""Tests for payment CRUD: provider id binding and idempotent paid transition."""
import os
import pytest
import asyncio

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from bot.db.models import Base
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
async def test_create_payment_starts_pending_without_provider_id(session):
    await crud.get_or_create_user(session, telegram_id=401)
    payment = await crud.create_payment(session, 401, 199, "month")
    assert payment.status == "pending"
    assert payment.provider_payment_id is None


@pytest.mark.asyncio
async def test_set_provider_id_then_lookup(session):
    await crud.get_or_create_user(session, telegram_id=402)
    payment = await crud.create_payment(session, 402, 990, "year")
    await crud.set_payment_provider_id(session, payment.id, "yk_2c8f_402")

    found = await crud.get_payment_by_provider_id(session, "yk_2c8f_402")
    assert found is not None
    assert found.amount == 990
    assert found.plan == "year"


@pytest.mark.asyncio
async def test_mark_payment_paid_first_call_returns_payment(session):
    await crud.get_or_create_user(session, telegram_id=403)
    payment = await crud.create_payment(session, 403, 199, "month")
    await crud.set_payment_provider_id(session, payment.id, "yk_pay_403")

    claimed = await crud.mark_payment_paid(session, "yk_pay_403")
    assert claimed is not None
    assert claimed.status == "paid"


@pytest.mark.asyncio
async def test_mark_payment_paid_replay_returns_none(session):
    """A replayed YooKassa webhook must not grant the purchase twice."""
    await crud.get_or_create_user(session, telegram_id=404)
    payment = await crud.create_payment(session, 404, 199, "month")
    await crud.set_payment_provider_id(session, payment.id, "yk_pay_404")

    first = await crud.mark_payment_paid(session, "yk_pay_404")
    second = await crud.mark_payment_paid(session, "yk_pay_404")
    third = await crud.mark_payment_paid(session, "yk_pay_404")

    assert first is not None
    assert second is None
    assert third is None


@pytest.mark.asyncio
async def test_mark_payment_paid_unknown_provider_id(session):
    assert await crud.mark_payment_paid(session, "yk_does_not_exist") is None
