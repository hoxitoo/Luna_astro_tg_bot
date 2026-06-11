"""Tests for payment CRUD: collision-free InvId and idempotent paid transition."""
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
async def test_create_payment_inv_id_equals_row_id(session):
    await crud.get_or_create_user(session, telegram_id=401)
    payment = await crud.create_payment(session, 401, 199, "month")
    assert payment.robokassa_inv_id == payment.id
    assert payment.status == "pending"


@pytest.mark.asyncio
async def test_create_payment_inv_ids_unique(session):
    await crud.get_or_create_user(session, telegram_id=402)
    p1 = await crud.create_payment(session, 402, 199, "month")
    p2 = await crud.create_payment(session, 402, 990, "year")
    assert p1.robokassa_inv_id != p2.robokassa_inv_id


@pytest.mark.asyncio
async def test_mark_payment_paid_first_call_returns_payment(session):
    await crud.get_or_create_user(session, telegram_id=403)
    payment = await crud.create_payment(session, 403, 199, "month")

    claimed = await crud.mark_payment_paid(session, payment.robokassa_inv_id)
    assert claimed is not None
    assert claimed.status == "paid"


@pytest.mark.asyncio
async def test_mark_payment_paid_replay_returns_none(session):
    """A replayed Robokassa callback must not grant the purchase twice."""
    await crud.get_or_create_user(session, telegram_id=404)
    payment = await crud.create_payment(session, 404, 199, "month")

    first = await crud.mark_payment_paid(session, payment.robokassa_inv_id)
    second = await crud.mark_payment_paid(session, payment.robokassa_inv_id)
    third = await crud.mark_payment_paid(session, payment.robokassa_inv_id)

    assert first is not None
    assert second is None
    assert third is None


@pytest.mark.asyncio
async def test_mark_payment_paid_unknown_inv_id(session):
    assert await crud.mark_payment_paid(session, 999999) is None


@pytest.mark.asyncio
async def test_get_payment_by_inv_id(session):
    await crud.get_or_create_user(session, telegram_id=405)
    payment = await crud.create_payment(session, 405, 99, "pack")
    found = await crud.get_payment_by_inv_id(session, payment.robokassa_inv_id)
    assert found is not None
    assert found.amount == 99
    assert found.plan == "pack"
