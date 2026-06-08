# 🌙 Luna — Telegram Tarot & Astrology Bot

Telegram-бот для гаданий на таро и гороскопов. Персонаж — Луна, мистический таролог.

## Стек
- Python 3.11 + aiogram 3.x
- PostgreSQL 15 + SQLAlchemy 2.0 async
- Claude API (claude-sonnet-4)
- Redis (FSM + кеш)
- Robokassa (платежи RU/BY/KZ)
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
| `ROBOKASSA_LOGIN` | Логин из кабинета Robokassa |
| `ROBOKASSA_PASSWORD1` | Password1 из Robokassa |
| `ROBOKASSA_PASSWORD2` | Password2 из Robokassa |
| `ROBOKASSA_TEST_MODE` | True для тестов, False для продакшна |

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
│   └── payment_service.py   # Robokassa
├── db/                  # БД (models, crud, session)
└── keyboards/           # Inline keyboards
data/
├── tarot_cards.json     # 78 карт таро
└── zodiac_signs.json    # 12 знаков зодиака
```
