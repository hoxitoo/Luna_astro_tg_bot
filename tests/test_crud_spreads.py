"""Tests for spread CRUD (save_spread, get_spreads_page, get_spread_by_id, birthday matching)."""
import os
import pytest
import asyncio
from datetime import date, datetime, timezone

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
async def test_save_spread_basic(session):
    await crud.get_or_create_user(session, telegram_id=301)
    spread = await crud.save_spread(
        session, 301, "tarot_3", "Карты говорят...",
        question="Что меня ждёт?",
        cards_json=[{"id": 1, "name_ru": "Маг", "reversed": False}]
    )
    assert spread.id is not None
    assert spread.user_id == 301
    assert spread.spread_type == "tarot_3"
    assert spread.interpretation == "Карты говорят..."
    assert spread.question == "Что меня ждёт?"


@pytest.mark.asyncio
async def test_get_spreads_page_returns_saved(session):
    await crud.get_or_create_user(session, telegram_id=302)
    for i in range(3):
        await crud.save_spread(session, 302, "tarot_3", f"Интерпретация {i}")

    spreads, total = await crud.get_spreads_page(session, 302, page=1)
    assert total == 3
    assert len(spreads) == 3


@pytest.mark.asyncio
async def test_get_spreads_page_pagination(session):
    await crud.get_or_create_user(session, telegram_id=303)
    for i in range(10):
        await crud.save_spread(session, 303, "tarot_3", f"Spread {i}")

    page1, total = await crud.get_spreads_page(session, 303, page=1, per_page=8)
    page2, _ = await crud.get_spreads_page(session, 303, page=2, per_page=8)
    assert total == 10
    assert len(page1) == 8
    assert len(page2) == 2


@pytest.mark.asyncio
async def test_get_spread_by_id_correct_user(session):
    await crud.get_or_create_user(session, telegram_id=304)
    spread = await crud.save_spread(session, 304, "past", "Прошлое...")
    found = await crud.get_spread_by_id(session, spread.id, user_id=304)
    assert found is not None
    assert found.id == spread.id


@pytest.mark.asyncio
async def test_get_spread_by_id_wrong_user_returns_none(session):
    await crud.get_or_create_user(session, telegram_id=305)
    await crud.get_or_create_user(session, telegram_id=306)
    spread = await crud.save_spread(session, 305, "past", "Прошлое...")
    # user 306 tries to access user 305's spread
    found = await crud.get_spread_by_id(session, spread.id, user_id=306)
    assert found is None


@pytest.mark.asyncio
async def test_get_spreads_page_empty(session):
    await crud.get_or_create_user(session, telegram_id=307)
    spreads, total = await crud.get_spreads_page(session, 307, page=1)
    assert total == 0
    assert spreads == []
