import json
import random
from pathlib import Path


class CardEngine:
    def __init__(self):
        data = json.loads(Path("data/tarot_cards.json").read_text(encoding="utf-8"))
        self.cards = data["cards"]

    def draw(self, n: int = 3) -> list[dict]:
        drawn = random.sample(self.cards, n)
        result = []
        for card in drawn:
            c = dict(card)
            c["reversed"] = random.choice([True, False])
            result.append(c)
        return result


card_engine = CardEngine()
