"""Tests for Three Moons persona system (claude_service._persona_prefix)."""
import os
import sys
import types

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

# Stub out anthropic so claude_service imports cleanly without the real library
_anthropic_stub = types.ModuleType("anthropic")
_anthropic_stub.AsyncAnthropic = object
sys.modules.setdefault("anthropic", _anthropic_stub)

from bot.services.claude_service import _persona_prefix, _PERSONA_BLOCKS


def test_young_moon_is_default():
    result = _persona_prefix(None)
    assert result == _PERSONA_BLOCKS["young_moon"]


def test_young_moon_by_key():
    assert _persona_prefix("young_moon") == _PERSONA_BLOCKS["young_moon"]


def test_full_moon_by_key():
    assert _persona_prefix("full_moon") == _PERSONA_BLOCKS["full_moon"]


def test_dark_moon_by_key():
    assert _persona_prefix("dark_moon") == _PERSONA_BLOCKS["dark_moon"]


def test_unknown_persona_falls_back_to_young_moon():
    assert _persona_prefix("unknown_persona") == _PERSONA_BLOCKS["young_moon"]


def test_all_personas_non_empty():
    for key, block in _PERSONA_BLOCKS.items():
        assert block.strip(), f"Persona block '{key}' is empty"


def test_personas_are_different():
    blocks = list(_PERSONA_BLOCKS.values())
    for i, b1 in enumerate(blocks):
        for j, b2 in enumerate(blocks):
            if i != j:
                assert b1 != b2, "Two persona blocks are identical"
