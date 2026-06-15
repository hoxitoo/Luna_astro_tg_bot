# 🌙 Luna — Telegram Tarot & Astrology Bot

Telegram-бот для гаданий на таро и гороскопов. Персонаж — Луна, мистический таролог.

- **Бот:** [@luna_reads_bot](https://t.me/luna_reads_bot)
- **Лендинг:** https://hoxitoo.github.io/Luna_astro_tg_bot/ (ветка `gh-pages`)

## Стек
- Python 3.11 + aiogram 3.x
- PostgreSQL 15 + SQLAlchemy 2.0 async
- Claude API (claude-sonnet-4)
- Redis (FSM + кеш)
- Telegram Stars + Robokassa (платежи RU); ЮKassa-код готов на будущее
- Docker + docker-compose

## Быстрый старт

```bash
# 1. Скопируй .env.example в .env и заполни токены
cp .env.example .env
nano .env

# 2. Запусти через Docker
docker-compose up -d

# 3. Смотри логи
docker-compose logs -f bot
```

## Переменные окружения (.env)

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Telegram bot token от @BotFather |
| `CLAUDE_API_KEY` | Ключ от console.anthropic.com |
| `DATABASE_URL` | postgresql+asyncpg://... |
| `REDIS_URL` | redis://redis:6379/0 |
| `STARS_PRICE_MONTH` / `STARS_PRICE_YEAR` | Цены подписки в Telegram Stars |
| `ROBOKASSA_LOGIN` / `ROBOKASSA_PASSWORD1` / `ROBOKASSA_PASSWORD2` | Из кабинета Robokassa |
| `ROBOKASSA_TEST_MODE` | True для тестов, False для продакшна |
| `YOOKASSA_*` | На будущее — сейчас не используется |

## Структура

```
bot/
├── main.py              # Точка входа
├── config.py            # Настройки (pydantic-settings)
├── handlers/            # aiogram роутеры
├── services/            # Бизнес-логика
│   ├── claude_service.py    # Все 7 типов промптов
│   ├── card_engine.py       # Раздача карт
│   ├── limit_service.py     # Лимиты бесплатных раскладов
│   └── payment_service.py   # Robokassa (Stars — в handlers/payment.py)
├── db/                  # БД (models, crud, session)
└── keyboards/           # Inline keyboards
data/
├── tarot_cards.json     # 78 карт таро
└── zodiac_signs.json    # 12 знаков зодиака
```

## Ветки

- **`main`** — код бота.
- **`gh-pages`** — статический сайт (лендинг + юридические страницы), публикуется через GitHub Pages.

## Документация

- [docs/DEPLOY_REGRU.md](docs/DEPLOY_REGRU.md) — деплой на VPS reg.ru (Stars + Robokassa).
- [docs/PRIVACY_POLICY.md](docs/PRIVACY_POLICY.md) — политика конфиденциальности (152-ФЗ).
- Лендинг и страницы `privacy.html` / `terms.html` живут в ветке `gh-pages`.

## GitHub Pages

Включить один раз: **Settings → Pages → Source: Deploy from a branch → `gh-pages` / `(root)`**.
После этого сайт доступен на https://hoxitoo.github.io/Luna_astro_tg_bot/.
