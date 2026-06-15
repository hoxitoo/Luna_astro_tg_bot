"""Shared pytest fixtures."""
import os
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta

# Set dummy env vars before any bot imports
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ROBOKASSA_LOGIN", "TestShop")
os.environ.setdefault("ROBOKASSA_PASSWORD1", "pass1")
os.environ.setdefault("ROBOKASSA_PASSWORD2", "pass2")
os.environ.setdefault("YOOKASSA_SHOP_ID", "123456")
os.environ.setdefault("YOOKASSA_SECRET_KEY", "test_secret")


def make_user(
    telegram_id: int = 1,
    name: str = "Тест",
    zodiac_sign: str = "Овен",
    is_pro: bool = False,
    pro_until=None,
    extra_spreads: int = 0,
):
    """Create a lightweight User-like object for tests (no DB session needed)."""
    return SimpleNamespace(
        telegram_id=telegram_id,
        username=None,
        name=name,
        birth_date=None,
        zodiac_sign=zodiac_sign,
        is_pro=is_pro,
        pro_until=pro_until,
        extra_spreads=extra_spreads,
        created_at=datetime.now(timezone.utc),
    )


def make_pro_user(**kwargs):
    return make_user(
        is_pro=True,
        pro_until=datetime.now(timezone.utc) + timedelta(days=30),
        **kwargs,
    )


def make_expired_user(**kwargs):
    return make_user(
        is_pro=True,
        pro_until=datetime.now(timezone.utc) - timedelta(days=1),
        **kwargs,
    )
