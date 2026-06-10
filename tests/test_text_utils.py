"""Tests for bot/utils/text_utils.py."""
import os

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from bot.utils.text_utils import (
    escape_md1,
    escape_md2,
    zodiac_with_emoji,
    truncate,
    card_display_name,
    cards_line,
    ZODIAC_EMOJI,
)


# --- escape_md1 ---

def test_escape_md1_bold_star():
    assert escape_md1("hello *world*") == r"hello \*world\*"


def test_escape_md1_underscore():
    assert escape_md1("_italic_") == r"\_italic\_"


def test_escape_md1_safe_text():
    assert escape_md1("просто текст") == "просто текст"


def test_escape_md1_backtick():
    assert escape_md1("`code`") == r"\`code\`"


# --- escape_md2 ---

def test_escape_md2_dot():
    assert escape_md2("v1.0") == r"v1\.0"


def test_escape_md2_exclamation():
    assert escape_md2("wow!") == r"wow\!"


def test_escape_md2_parens():
    assert escape_md2("(ok)") == r"\(ok\)"


# --- zodiac_with_emoji ---

def test_zodiac_aries():
    assert zodiac_with_emoji("Овен") == "♈ Овен"


def test_zodiac_all_signs_have_emoji():
    from bot.utils.text_utils import ZODIAC_EMOJI
    for sign in ZODIAC_EMOJI:
        result = zodiac_with_emoji(sign)
        assert result.startswith(ZODIAC_EMOJI[sign])
        assert sign in result


def test_zodiac_unknown_sign():
    assert zodiac_with_emoji("Дракон") == "Дракон"


# --- truncate ---

def test_truncate_short_text():
    assert truncate("hello") == "hello"


def test_truncate_exact_limit():
    text = "x" * 4096
    assert truncate(text) == text


def test_truncate_over_limit():
    text = "x" * 5000
    result = truncate(text)
    assert len(result) == 4096
    assert result.endswith("...")


def test_truncate_custom_limit():
    result = truncate("abcdefgh", max_len=5)
    assert result == "ab..."
    assert len(result) == 5


# --- card_display_name ---

def test_card_display_name_upright():
    card = {"name_ru": "Луна", "reversed": False}
    assert card_display_name(card) == "Луна"


def test_card_display_name_reversed():
    card = {"name_ru": "Луна", "reversed": True}
    assert card_display_name(card) == "Луна ↓"


def test_card_display_name_fallback_to_name():
    card = {"name": "The Moon", "reversed": False}
    assert card_display_name(card) == "The Moon"


# --- cards_line ---

def test_cards_line_three_cards():
    cards = [
        {"name_ru": "Луна", "reversed": False},
        {"name_ru": "Солнце", "reversed": True},
        {"name_ru": "Мир", "reversed": False},
    ]
    assert cards_line(cards) == "Луна · Солнце ↓ · Мир"


def test_cards_line_custom_separator():
    cards = [
        {"name_ru": "A", "reversed": False},
        {"name_ru": "B", "reversed": False},
    ]
    assert cards_line(cards, separator=" | ") == "A | B"


def test_cards_line_empty():
    assert cards_line([]) == ""
