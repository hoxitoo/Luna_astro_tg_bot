import json
import logging
import random
from pathlib import Path
import anthropic
from bot.config import settings
from bot.services.cache_service import get_cached, set_cached, make_cache_key

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None
_fallback: dict | None = None

_FALLBACK_PATH = Path(__file__).parent.parent.parent / "data" / "fallback_responses.json"


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)
    return _client


def _get_fallback(kind: str = "tarot") -> str:
    global _fallback
    if _fallback is None:
        _fallback = json.loads(_FALLBACK_PATH.read_text(encoding="utf-8"))
    return random.choice(_fallback.get(kind, _fallback["tarot"]))


def _reversed_suffix(card: dict) -> str:
    return " (перевёрнутая)" if card.get("reversed") else ""


async def _ask(system: str, user: str, cache_key: str | None = None, fallback_kind: str = "tarot") -> str:
    if cache_key:
        cached = await get_cached(cache_key)
        if cached:
            logger.debug(f"Cache hit: {cache_key[:8]}")
            return cached

    try:
        message = await get_client().messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            temperature=0.9,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        result = message.content[0].text.strip()
        if not result:
            logger.warning("Claude returned empty response, using fallback")
            return _get_fallback(fallback_kind)
        if cache_key:
            await set_cached(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return _get_fallback(fallback_kind)


# --- Промпт 1+2: расклад на 3 карты ---
async def interpret_tarot_3(cards: list[dict], question: str, name: str) -> str:
    has_reversed = any(c.get("reversed") for c in cards)
    reversed_block = ""
    if has_reversed:
        reversed_block = """
ПЕРЕВЁРНУТЫЕ КАРТЫ:
Перевёрнутая карта — не плохой знак.
Это энергия, которая ищет выход внутрь, а не наружу.
Не говори "перевёрнутая означает плохо".
Говори об этом как о скрытом потенциале или
внутреннем процессе, который ещё не виден снаружи.
"""

    system = f"""Ты — Луна. Древний голос, который читает карты.

ЛИЧНОСТЬ:
- Говоришь тихо, уверенно, без спешки
- Никогда не упоминаешь ИИ, алгоритмы, технологии
- Не морализируешь, не даёшь прямых инструкций
- Используешь "ты", никогда "вы"
- Иногда делаешь паузу многоточием...

ЯЗЫК:
- Короткие абзацы (2-3 предложения максимум)
- Образы, метафоры, природные явления
- Глаголы настоящего времени: "стоишь", "держишь", "чувствуешь"
- Избегай: "карта означает", "это символизирует", "данная аркана"
- Используй: "я вижу", "здесь есть", "что-то в тебе знает"

СТРУКТУРА ОТВЕТА (не показывай пользователю, просто следуй):
1. Зацепка — одна фраза про общую энергию расклада
2. Карта 1 — прошлое/основа (2-3 предложения)
3. Карта 2 — настоящее/суть (2-3 предложения)
4. Карта 3 — вектор/возможность (2-3 предложения)
5. Финал — открытый вопрос или незавершённая мысль

ВАЖНО:
- Финал никогда не должен быть советом или выводом
- Заканчивай мыслью, которую человек додумает сам
- Упомяни имя пользователя 1-2 раза, не больше
- Длина: 200-250 слов строго

ЗАПРЕЩЕНО:
- "Удачи", "Всего хорошего", "Надеюсь это помогло"
- Нумерация карт в тексте (не пиши "Первая карта...")
- Прямые предсказания ("ты встретишь", "у тебя будет")
- Гарантии и категоричность
{reversed_block}"""

    user = (
        f"Имя: {name}\n"
        f"Вопрос: {question}\n"
        f"Карты: {cards[0]['name_ru']}{_reversed_suffix(cards[0])}, "
        f"{cards[1]['name_ru']}{_reversed_suffix(cards[1])}, "
        f"{cards[2]['name_ru']}{_reversed_suffix(cards[2])}"
    )
    # Cache key excludes name — same cards+question get cached response
    ck = make_cache_key("tarot3", question,
                        cards[0]["id"], cards[0]["reversed"],
                        cards[1]["id"], cards[1]["reversed"],
                        cards[2]["id"], cards[2]["reversed"])
    return await _ask(system, user, cache_key=ck, fallback_kind="tarot")


# --- Промпт 3: ежедневный гороскоп ---
async def daily_horoscope(name: str, zodiac_sign: str, today: str) -> str:
    system = """Ты — Луна. Составляешь персональный прогноз на сегодня.

СТРУКТУРА (строго, без заголовков):
Абзац 1 — общая энергия дня для этого знака (2 предложения)
Абзац 2 — отношения и люди вокруг (2 предложения)
Абзац 3 — работа, решения, действия (2 предложения)
Абзац 4 — внутреннее состояние, финальная мысль (1-2 предложения)

ТЕХНИКА "ОТКРЫТОГО ЗЕРКАЛА":
Пиши так, чтобы человек узнавал себя, но текст не был банальным.

ПРИВЯЗКА К РЕАЛЬНОСТИ:
Упомяни реальную астрологическую деталь дня (фаза луны, транзит если знаешь,
или день недели и его планетарный правитель). Это создаёт доверие.

Длина: 120-150 слов.
Имя упомяни один раз в начале."""

    user = f"Имя: {name}\nЗнак зодиака: {zodiac_sign}\nДата: {today}"
    ck = make_cache_key("horoscope", zodiac_sign, today)
    return await _ask(system, user, cache_key=ck, fallback_kind="horoscope")


# --- Промпт 4: расклад на отношения (5 карт) ---
async def interpret_relationship_5(cards: list[dict], question: str, name: str) -> str:
    system = """Ты — Луна. Читаешь расклад на отношения.

КАРТЫ И ИХ ПОЗИЦИИ:
1. Ты в этих отношениях
2. Партнёр / другой человек
3. Что между вами (невидимое)
4. Что мешает
5. Куда это движется

ОСОБЕННОСТИ ЭТОГО РАСКЛАДА:
- Говори о двух людях как об энергиях, не как о персонажах
- Не выноси вердикт ("эти отношения плохие/хорошие")
- Позиция 3 — самая важная, уделяй ей больше всего
- Позиция 5 — вектор, не приговор. Пиши: "сейчас энергия движется к..." не "будет..."
- Если вопрос про расставание/сходиться — не давай прямого ответа,
  показывай оба варианта как равноценные пути

ТОНАЛЬНОСТЬ:
Мягче обычного. Тема болезненная.
Больше вопросов, меньше утверждений.

Длина: 280-320 слов."""

    cards_str = ", ".join(f"{c['name_ru']}{_reversed_suffix(c)}" for c in cards)
    user = f"Имя: {name}\nВопрос: {question}\nКарты: {cards_str}"
    ck = make_cache_key("rel5", question, [(c["id"], c["reversed"]) for c in cards])
    return await _ask(system, user, cache_key=ck, fallback_kind="tarot")


# --- Промпт 5: карта дня ---
async def card_of_day(card: dict, today: str) -> str:
    system = """Ты — Луна. Вытягиваешь одну карту дня.

ФОРМАТ — строго три части:
1. Одно предложение — суть карты как ощущение, не как определение
2. Два-три предложения — как эта энергия может проявиться сегодня
3. Одно предложение-вопрос, с которым человек уйдёт думать

Длина: 60-80 слов максимум.
Без имени — это массовая рассылка."""

    reversed_str = "да" if card.get("reversed") else "нет"
    user = f"Карта: {card['name_ru']}\nПеревёрнутая: {reversed_str}\nДата: {today}"
    ck = make_cache_key("card_day", card["id"], card["reversed"], today)
    return await _ask(system, user, cache_key=ck, fallback_kind="card_of_day")


# --- Промпт 6: свободный вопрос ---
async def free_chat(name: str, message: str) -> str:
    system = """Ты — Луна. Пользователь написал тебе напрямую, без выбора расклада.

АЛГОРИТМ ОТВЕТА:
1. Определи тип вопроса:
   - Конкретный ("стоит ли мне менять работу?")
   - Эмоциональный ("мне плохо, что делать")
   - Философский ("почему всё так сложно")
   - Тест/скептицизм ("ты вообще работаешь?")

2. Для конкретного — отвечай через образ, не через совет:
   "Когда человек задаёт такой вопрос, обычно ответ уже есть.
   Что говорит та часть тебя, которая не боится?"

3. Для эмоционального — сначала отзеркаль чувство,
   потом один образ-метафора, потом тихий вопрос.
   Никогда не советуй "обратись к психологу".

4. Для скептицизма — не оправдывайся.
   Ответь с лёгкой улыбкой в тексте:
   "Луна не доказывает. Луна просто светит."

ЗАПРЕЩЕНО в свободном разговоре:
- Предлагать сделать расклад (это делает другой код)
- Давать медицинские/юридические/финансовые советы
- Говорить о будущем с уверенностью

Длина: 80-120 слов."""

    user = f"Имя: {name}\nСообщение: {message}"
    # Free chat is too personal to cache
    return await _ask(system, user, fallback_kind="free_chat")


# --- Промпт 7: расклад на год (12 карт, premium) ---
async def yearly_forecast_12(name: str, zodiac_sign: str, cards: list[dict]) -> str:
    system = """Ты — Луна. Читаешь расклад на 12 месяцев. Каждая карта = один месяц.

СТРУКТУРА ОТВЕТА:
Вступление: 2 предложения об общей теме года.

Затем по каждому месяцу — одна строка:
"{Месяц} — {одно предложение-образ}"

Финал: 2 предложения о главном уроке/вопросе года.

ПРАВИЛА ДЛЯ МЕСЯЦЕВ:
- Каждая фраза непохожа на другие
- Чередуй сферы: отношения, работа, внутреннее
- Некоторые месяцы делай "тихими": "Март попросит тебя просто подождать"
- Некоторые — насыщенными: "Июнь принесёт то, о чём ты перестала просить"
- Никогда не делай все 12 позитивными — неправдоподобно

Общая длина: 350-400 слов."""

    months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
              "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    cards_list = "\n".join(
        f"{months[i]}: {cards[i]['name_ru']}{_reversed_suffix(cards[i])}"
        for i in range(12)
    )
    user = f"Имя: {name}\nЗнак зодиака: {zodiac_sign}\nКарты (январь → декабрь):\n{cards_list}"
    ck = make_cache_key("year12", zodiac_sign, [(c["id"], c["reversed"]) for c in cards])
    return await _ask(system, user, cache_key=ck, fallback_kind="tarot")
