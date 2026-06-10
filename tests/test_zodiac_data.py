"""Tests for zodiac_signs.json — structure and content validity."""
import os
import json
from pathlib import Path

os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault("CLAUDE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

ZODIAC_PATH = Path(__file__).parent.parent / "data" / "zodiac_signs.json"
REQUIRED_SIGN_KEYS = {"name", "element", "planet", "dates", "traits"}
EXPECTED_SIGNS = {
    "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
    "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы",
}
ELEMENTS = {"огонь", "земля", "воздух", "вода"}


def load():
    return json.loads(ZODIAC_PATH.read_text(encoding="utf-8"))


def test_zodiac_file_exists():
    assert ZODIAC_PATH.exists()


def test_zodiac_has_12_signs():
    data = load()
    signs = data.get("signs", data) if isinstance(data, dict) and "signs" in data else data
    assert len(signs) == 12, f"Expected 12 signs, got {len(signs)}"


def test_zodiac_all_names_present():
    data = load()
    signs = data.get("signs", data) if isinstance(data, dict) and "signs" in data else data
    names = {s["name"] for s in signs}
    missing = EXPECTED_SIGNS - names
    assert not missing, f"Missing signs: {missing}"


def test_zodiac_required_fields():
    data = load()
    signs = data.get("signs", data) if isinstance(data, dict) and "signs" in data else data
    for sign in signs:
        missing = REQUIRED_SIGN_KEYS - set(sign.keys())
        assert not missing, f"Sign '{sign.get('name')}' missing fields: {missing}"


def test_zodiac_valid_elements():
    data = load()
    signs = data.get("signs", data) if isinstance(data, dict) and "signs" in data else data
    for sign in signs:
        assert sign["element"] in ELEMENTS, \
            f"Sign '{sign['name']}' has invalid element: {sign['element']}"


def test_zodiac_traits_non_empty():
    data = load()
    signs = data.get("signs", data) if isinstance(data, dict) and "signs" in data else data
    for sign in signs:
        traits = sign.get("traits", [])
        assert isinstance(traits, list) and len(traits) >= 1, \
            f"Sign '{sign['name']}' has no traits"


def test_zodiac_dates_non_empty():
    data = load()
    signs = data.get("signs", data) if isinstance(data, dict) and "signs" in data else data
    for sign in signs:
        assert sign.get("dates"), f"Sign '{sign['name']}' has empty dates"
