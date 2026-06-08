import pytest
import sys
import os

# Allow import without .env present
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("CLAUDE_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from bot.services.card_engine import CardEngine


@pytest.fixture
def engine():
    return CardEngine()


def test_draw_returns_correct_count(engine):
    for n in (1, 3, 5, 12):
        cards = engine.draw(n)
        assert len(cards) == n


def test_draw_no_duplicates(engine):
    cards = engine.draw(10)
    ids = [c["id"] for c in cards]
    assert len(ids) == len(set(ids))


def test_draw_has_reversed_field(engine):
    cards = engine.draw(3)
    for card in cards:
        assert "reversed" in card
        assert isinstance(card["reversed"], bool)


def test_draw_has_name_ru(engine):
    cards = engine.draw(3)
    for card in cards:
        assert "name_ru" in card
        assert len(card["name_ru"]) > 0


def test_total_cards_is_78(engine):
    assert len(engine.cards) == 78


def test_draw_does_not_mutate_deck(engine):
    original_count = len(engine.cards)
    engine.draw(5)
    assert len(engine.cards) == original_count


def test_reversed_is_random_over_many_draws(engine):
    """At least some reversed, some upright over 50 draws."""
    results = [engine.draw(1)[0]["reversed"] for _ in range(50)]
    assert True in results
    assert False in results
