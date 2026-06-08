# Luna (AstroBot) — Claude Code Instructions

## Project Overview
Telegram bot «Луна» — мистический таролог и астролог.
Бесплатно: 3 расклада в день. Платно (199 ₽/мес): безлимит + гороскоп + карта дня.
AI-интерпретации генерируются через Claude API.

## Tech Stack
- Python 3.11 + aiogram 3.x (async)
- PostgreSQL 15 + SQLAlchemy 2.0 async + Alembic
- Claude API: claude-sonnet-4-20250514, temperature=0.9, max_tokens=600
- Redis — FSMContext storage + кеш интерпретаций (TTL 24ч)
- Robokassa — оплата для RU/BY/KZ
- Docker + docker-compose

## Key Rules
- ВСЕ хэндлеры — async
- FSMContext для multi-step flows (вопрос → карты → интерпретация)
- Никогда не хардкодить API ключи — только .env + config.py
- DB операции только через bot/db/crud.py
- Вызовы Claude API только через bot/services/claude_service.py
- Только inline keyboards (не reply keyboards)
- Бот всегда называет себя «Луна», никогда не упоминает ИИ

## Free Limits
- 3 расклада таро в день на пользователя
- 1 персональный гороскоп в день
- Сброс лимита в 00:00 МСК
- Pro-пользователи: безлимит

## Persona
Луна говорит тихо, уверенно, без спешки.
Короткие абзацы. Образы и метафоры.
Никогда: "Удачи", "Всего хорошего", нумерация карт.
Всегда на "ты".

## File Responsibilities
- bot/services/claude_service.py — все 7 типов промптов
- bot/services/card_engine.py — CardEngine.draw(n), поддержка reversed
- bot/services/limit_service.py — check_limit, increment_limit
- bot/services/payment_service.py — Robokassa URL + MD5 verify
- bot/db/crud.py — get_or_create_user, get_daily_limit, set_pro
