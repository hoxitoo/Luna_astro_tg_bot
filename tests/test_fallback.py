"""Tests for fallback_responses.json — structure and content validity."""
import os
import json
from pathlib import Path

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

FALLBACK_PATH = Path(__file__).parent.parent / "data" / "fallback_responses.json"
REQUIRED_KEYS = {"tarot", "horoscope", "card_of_day", "free_chat"}


def load():
    return json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))


def test_fallback_file_exists():
    assert FALLBACK_PATH.exists()


def test_fallback_has_required_keys():
    data = load()
    assert REQUIRED_KEYS.issubset(data.keys())


def test_fallback_lists_non_empty():
    data = load()
    for key in REQUIRED_KEYS:
        assert len(data[key]) >= 1, f"fallback['{key}'] is empty"


def test_fallback_all_strings():
    data = load()
    for key, responses in data.items():
        for i, r in enumerate(responses):
            assert isinstance(r, str) and len(r) > 10, \
                f"fallback['{key}'][{i}] is too short or not a string"


def test_fallback_tarot_has_enough_variety():
    data = load()
    assert len(data["tarot"]) >= 5, "Need at least 5 tarot fallbacks for variety"
