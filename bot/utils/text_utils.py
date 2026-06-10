"""
Text formatting utilities for Telegram Markdown and Luna-specific display helpers.

Telegram MarkdownV1 special chars that must NOT appear unescaped in *italic* / *bold*:
  *  _  `  [

For safety, use these helpers when inserting user-supplied strings into formatted messages.
"""

import re

# Characters Telegram MarkdownV1 treats as formatting triggers
_MD1_ESCAPE_RE = re.compile(r"([*_`\[])")

# MarkdownV2 requires escaping a wider set
_MD2_ESCAPE_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")

ZODIAC_EMOJI: dict[str, str] = {
    "Овен": "♈",
    "Телец": "♉",
    "Близнецы": "♊",
    "Рак": "♋",
    "Лев": "♌",
    "Дева": "♍",
    "Весы": "♎",
    "Скорпион": "♏",
    "Стрелец": "♐",
    "Козерог": "♑",
    "Водолей": "♒",
    "Рыбы": "♓",
}


def escape_md1(text: str) -> str:
    """Escape user-supplied text for safe insertion in MarkdownV1 messages."""
    return _MD1_ESCAPE_RE.sub(r"\\\1", text)


def escape_md2(text: str) -> str:
    """Escape user-supplied text for safe insertion in MarkdownV2 messages."""
    return _MD2_ESCAPE_RE.sub(r"\\\1", text)


def zodiac_with_emoji(sign: str) -> str:
    """Return zodiac sign name with its emoji prefix, e.g. '♈ Овен'."""
    emoji = ZODIAC_EMOJI.get(sign, "")
    return f"{emoji} {sign}".strip() if emoji else sign


def truncate(text: str, max_len: int = 4096) -> str:
    """Truncate text to Telegram's max message length, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def card_display_name(card: dict) -> str:
    """
    Return a card's display name with reversed indicator.
    Example: 'Луна ↓' for a reversed Moon card.
    """
    name = card.get("name_ru", card.get("name", "?"))
    suffix = " ↓" if card.get("reversed") else ""
    return f"{name}{suffix}"


def cards_line(cards: list[dict], separator: str = " · ") -> str:
    """
    Join a list of card dicts into a single display line.
    Example: 'Луна ↓ · Солнце · Мир'
    """
    return separator.join(card_display_name(c) for c in cards)
