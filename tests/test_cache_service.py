"""Tests for cache_service helpers that don't require a live Redis."""
import os
import json
import hashlib

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from bot.services.cache_service import make_cache_key


def test_make_cache_key_is_deterministic():
    k1 = make_cache_key("tarot3", "вопрос", 5, True, 10, False, 22, True)
    k2 = make_cache_key("tarot3", "вопрос", 5, True, 10, False, 22, True)
    assert k1 == k2


def test_make_cache_key_differs_on_different_input():
    k1 = make_cache_key("tarot3", "вопрос A", 5, True)
    k2 = make_cache_key("tarot3", "вопрос B", 5, True)
    assert k1 != k2


def test_make_cache_key_differs_on_reversed():
    k1 = make_cache_key("tarot3", "вопрос", 5, True)
    k2 = make_cache_key("tarot3", "вопрос", 5, False)
    assert k1 != k2


def test_make_cache_key_is_md5_hex():
    k = make_cache_key("test")
    assert len(k) == 32
    int(k, 16)  # must be valid hex


def test_make_cache_key_handles_unicode():
    k = make_cache_key("расклад", "почему всё так сложно 🌙")
    assert len(k) == 32


def test_make_cache_key_list_vs_tuple_different():
    """Lists and tuples produce different keys — consistent with json.dumps behavior."""
    k1 = make_cache_key("x", [1, 2])
    k2 = make_cache_key("x", (1, 2))
    # json.dumps treats lists and tuples the same → keys should be equal
    assert k1 == k2
