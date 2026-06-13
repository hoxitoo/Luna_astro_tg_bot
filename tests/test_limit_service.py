import os
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("CLAUDE_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from bot.services.limit_service import is_pro_active


def _make_user(**kwargs):
    """Lightweight stand-in for User ORM object — no DB session needed."""
    defaults = dict(is_pro=False, pro_until=None, extra_spreads=0, telegram_id=1)
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_is_pro_active_false_by_default():
    user = _make_user()
    assert is_pro_active(user) is False


def test_is_pro_active_with_future_expiry():
    user = _make_user(
        is_pro=True,
        pro_until=datetime.now(timezone.utc) + timedelta(days=30)
    )
    assert is_pro_active(user) is True


def test_is_pro_active_with_past_expiry():
    user = _make_user(
        is_pro=True,
        pro_until=datetime.now(timezone.utc) - timedelta(days=1)
    )
    assert is_pro_active(user) is False


def test_is_pro_active_with_naive_future_expiry():
    """SQLite (dev) returns naive datetimes — must not raise naive/aware TypeError."""
    naive_future = datetime.utcnow() + timedelta(days=30)
    assert naive_future.tzinfo is None  # sanity
    user = _make_user(is_pro=True, pro_until=naive_future)
    assert is_pro_active(user) is True


def test_is_pro_active_with_naive_past_expiry():
    naive_past = datetime.utcnow() - timedelta(days=1)
    user = _make_user(is_pro=True, pro_until=naive_past)
    assert is_pro_active(user) is False


def test_is_pro_active_is_pro_true_but_no_expiry():
    """is_pro=True without pro_until — treat as not active (data inconsistency guard)."""
    user = _make_user(is_pro=True, pro_until=None)
    assert is_pro_active(user) is False


def test_is_pro_active_false_when_is_pro_false_despite_future_expiry():
    user = _make_user(
        is_pro=False,
        pro_until=datetime.now(timezone.utc) + timedelta(days=30)
    )
    assert is_pro_active(user) is False


def test_is_pro_active_exactly_at_expiry_boundary():
    """Just barely expired — should be False."""
    user = _make_user(
        is_pro=True,
        pro_until=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    assert is_pro_active(user) is False
