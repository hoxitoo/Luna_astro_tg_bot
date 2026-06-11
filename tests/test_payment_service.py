import hashlib
import os
from unittest.mock import patch, MagicMock

os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("CLAUDE_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from bot.services.payment_service import (
    generate_payment_url,
    verify_result_signature,
)

_MOCK_SETTINGS = MagicMock(
    ROBOKASSA_LOGIN="TestShop",
    ROBOKASSA_PASSWORD1="pass1",
    ROBOKASSA_PASSWORD2="pass2",
    ROBOKASSA_TEST_MODE=True,
)


def test_generate_payment_url_contains_required_params():
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        url = generate_payment_url(amount=199, inv_id=123456)
    assert "MerchantLogin=TestShop" in url
    assert "OutSum=199" in url
    assert "InvId=123456" in url
    assert "SignatureValue=" in url


def test_generate_payment_url_no_unsigned_shp_params():
    # Robokassa rejects requests with Shp_ params that aren't in the signature.
    # We don't send any Shp_ params at all — InvId binds the user via the DB.
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        url = generate_payment_url(amount=199, inv_id=123456)
    assert "Shp_" not in url


def test_generate_payment_url_test_mode_flag():
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        url = generate_payment_url(amount=199, inv_id=1)
    assert "IsTest=1" in url


def test_generate_payment_url_signature_correct():
    login, pwd1, amount, inv_id = "TestShop", "pass1", 199, 123456
    expected_sig = hashlib.md5(f"{login}:{amount}:{inv_id}:{pwd1}".encode()).hexdigest()
    with patch("bot.services.payment_service.settings", _MOCK_SETTINGS):
        url = generate_payment_url(amount=amount, inv_id=inv_id)
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
