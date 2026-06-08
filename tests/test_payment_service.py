import hashlib
import os
from unittest.mock import patch, MagicMock

os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("CLAUDE_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from bot.services.payment_service import (
    generate_inv_id,
    generate_payment_url,
    verify_result_signature,
)

_MOCK_SETTINGS = MagicMock(
    ROBOKASSA_LOGIN="TestShop",
    ROBOKASSA_PASSWORD1="pass1",
    ROBOKASSA_PASSWORD2="pass2",
    ROBOKASSA_TEST_MODE=True,
)


def test_generate_inv_id_range():
    for _ in range(100):
        inv = generate_inv_id()
        assert 100_000 <= inv <= 9_999_999


def test_generate_inv_id_unique():
    ids = {generate_inv_id() for _ in range(20)}
    assert len(ids) > 1  # not all the same


def test_generate_payment_url_contains_required_params():
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        url = generate_payment_url(user_id=42, amount=199, inv_id=123456)
    assert "MerchantLogin=TestShop" in url
    assert "OutSum=199" in url
    assert "InvId=123456" in url
    assert "SignatureValue=" in url


def test_generate_payment_url_test_mode_flag():
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        url = generate_payment_url(user_id=1, amount=199, inv_id=1)
    assert "IsTest=1" in url


def test_generate_payment_url_signature_correct():
    login, pwd1, amount, inv_id = "TestShop", "pass1", 199, 123456
    expected_sig = hashlib.md5(f"{login}:{amount}:{inv_id}:{pwd1}".encode()).hexdigest()
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        url = generate_payment_url(user_id=1, amount=amount, inv_id=inv_id)
    assert expected_sig in url


def test_verify_result_signature_valid():
    pwd2, amount, inv_id = "pass2", 199, 123456
    sig = hashlib.md5(f"{amount}:{inv_id}:{pwd2}".encode()).hexdigest()
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        assert verify_result_signature(str(amount), str(inv_id), sig) is True


def test_verify_result_signature_invalid():
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        assert verify_result_signature("199", "123456", "badsignature") is False


def test_verify_signature_case_insensitive():
    pwd2, amount, inv_id = "pass2", 199, 123456
    sig = hashlib.md5(f"{amount}:{inv_id}:{pwd2}".encode()).hexdigest().upper()
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        assert verify_result_signature(str(amount), str(inv_id), sig) is True
