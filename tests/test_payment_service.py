"""Tests for the YooKassa payment service (pure logic + mocked HTTP)."""
import base64
import os
import uuid
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("CLAUDE_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

import bot.services.payment_service as ps
from bot.services.payment_service import (
    _auth_header,
    _return_url,
    create_payment_link,
    PaymentError,
)

_MOCK_SETTINGS = MagicMock(
    YOOKASSA_SHOP_ID="123456",
    YOOKASSA_SECRET_KEY="test_secret",
    YOOKASSA_RETURN_URL="",
    BOT_USERNAME="luna_reads_bot",
)


def test_auth_header_is_basic_base64():
    with patch.object(ps, "settings", _MOCK_SETTINGS):
        header = _auth_header()
    assert header.startswith("Basic ")
    decoded = base64.b64decode(header.removeprefix("Basic ")).decode()
    assert decoded == "123456:test_secret"


def test_return_url_falls_back_to_bot_deeplink():
    with patch.object(ps, "settings", _MOCK_SETTINGS):
        assert _return_url() == "https://t.me/luna_reads_bot"


def test_return_url_prefers_configured_value():
    cfg = MagicMock(YOOKASSA_RETURN_URL="https://luna.example/ok", BOT_USERNAME="x")
    with patch.object(ps, "settings", cfg):
        assert _return_url() == "https://luna.example/ok"


def test_idempotence_key_is_stable_per_payment():
    ns = ps._IDEMPOTENCE_NS
    a = str(uuid.uuid5(ns, "luna-payment-42"))
    b = str(uuid.uuid5(ns, "luna-payment-42"))
    c = str(uuid.uuid5(ns, "luna-payment-43"))
    assert a == b      # retrying the same DB row → same key (no double charge)
    assert a != c      # different rows → different keys


class _FakeResp:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakeSession:
    def __init__(self, resp):
        self._resp = resp

    def post(self, *a, **k):
        return self._resp

    def get(self, *a, **k):
        return self._resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


@pytest.mark.asyncio
async def test_create_payment_link_returns_url_and_id():
    resp = _FakeResp(200, {
        "id": "2c8f1234-0001",
        "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/2c8f1234"},
    })
    with patch.object(ps, "settings", _MOCK_SETTINGS), \
         patch.object(ps.aiohttp, "ClientSession", lambda *a, **k: _FakeSession(resp)):
        url, pid = await create_payment_link(199, "Luna Pro", 42)
    assert url == "https://yoomoney.ru/checkout/2c8f1234"
    assert pid == "2c8f1234-0001"


@pytest.mark.asyncio
async def test_create_payment_link_raises_on_error_status():
    resp = _FakeResp(401, {"type": "error", "code": "invalid_credentials"})
    with patch.object(ps, "settings", _MOCK_SETTINGS), \
         patch.object(ps.aiohttp, "ClientSession", lambda *a, **k: _FakeSession(resp)):
        with pytest.raises(PaymentError):
            await create_payment_link(199, "Luna Pro", 42)
