"""Tests for question length validation (bot/utils/text_utils.py)."""
import os

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from bot.utils.text_utils import validate_question, MAX_QUESTION_LEN


def test_short_question_is_valid():
    assert validate_question("Что меня ждёт?") is None


def test_max_length_question_is_valid():
    assert validate_question("А" * MAX_QUESTION_LEN) is None


def test_over_max_length_returns_error():
    error = validate_question("А" * (MAX_QUESTION_LEN + 1))
    assert error is not None
    assert isinstance(error, str)


def test_empty_question_is_valid():
    assert validate_question("") is None


def test_error_message_mentions_limit():
    error = validate_question("X" * 600)
    assert "500" in error or "символ" in error.lower()
