# Деплой Луны на VPS reg.ru

Пошаговая инструкция: от заказа сервера до бота, работающего 24/7 с приёмом
платежей (Telegram Stars + Robokassa).

> **Про оплату:** Telegram Stars работают сразу после деплоя — им НЕ нужен ни
> домен, ни вебхук, ни торговый аккаунт. Домен и nginx (разделы 2, 8, 9)
> нужны ТОЛЬКО для Robokassa (карты/рубли). Если на старте хватает Stars —
> разделы 2, 8, 9 можно пропустить и вернуться к ним позже.

---

## 0. Что понадобится

- Аккаунт на reg.ru
- Домен (нужен только для Robokassa; для Stars не требуется)
- Заполненные `BOT_TOKEN`, `CLAUDE_API_KEY` (обязательно), `ROBOKASSA_*` (для карт)
- ~30–40 минут

---

## 1. Заказать VPS

1. Зайди в reg.ru → **Облачные серверы (VPS)**.
2. Конфигурация — минимум **2 vCPU / 2 ГБ RAM / 20–40 ГБ SSD** (с запасом под
   PostgreSQL + Redis + бот).
3. ОС: **Ubuntu 22.04 LTS**.
4. После создания запиши **IP-адрес** и **root-пароль** (придут на почту / в ЛК).

## 2. Привязать домен

1. Купи домен (reg.ru → Домены) или используй имеющийся.
2. В DNS-настройках домена создай **A-запись**: `@` → IP твоего VPS.
   (При желании ещё `www` → тот же IP.)
3. Подожди 15–60 минут, пока DNS обновится. Проверка: `ping ваш-домен.ru`
   должен отдавать IP сервера.

## 3. Подключиться к серверу

С Windows (PowerShell):

```powershell
ssh root@ВАШ_IP
```

При первом входе подтверди отпечаток (`yes`) и введи пароль.

## 4. Установить Docker

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin git
docker --version    # проверка
```

## 5. Забрать код

```bash
cd /opt
git clone https://github.com/hoxitoo/Luna_astro_tg_bot.git
cd Luna_astro_tg_bot
```

## 6. Создать `.env` для продакшена

```bash
cp .env.example .env
nano .env
```

Заполни (Ctrl+O сохранить, Ctrl+X выйти):

```
BOT_TOKEN=токен_от_BotFather
CLAUDE_API_KEY=ключ_anthropic
CLAUDE_MODEL=claude-sonnet-4-20250514

# Продакшен: PostgreSQL + Redis в Docker
DATABASE_URL=postgresql+asyncpg://luna:СИЛЬНЫЙ_ПАРОЛЬ@db:5432/luna_db
REDIS_URL=redis://redis:6379/0

# Telegram Stars (без ключей — через токен бота). Цены в Stars.
STARS_PRICE_MONTH=150
STARS_PRICE_YEAR=750

# Robokassa (карты/рубли) — из кабинета Robokassa
ROBOKASSA_LOGIN=ваш_логин
ROBOKASSA_PASSWORD1=пароль_1
ROBOKASSA_PASSWORD2=пароль_2
ROBOKASSA_TEST_MODE=False

# Домен с HTTPS — включает приём вебхука Robokassa (для Stars НЕ нужен)
WEBHOOK_HOST=https://ваш-домен.ru

ADMIN_IDS=[1065395448]
BOT_USERNAME=luna_reads_bot
```

> Если пока запускаешь только на Stars — оставь `ROBOKASSA_*` пустыми и
> `WEBHOOK_HOST=` пустым. Бот будет принимать звёзды без домена и nginx.

> Пароль PostgreSQL в `DATABASE_URL` должен совпадать с тем, что в
> `docker-compose.yml` у сервиса `db` (переменная `POSTGRES_PASSWORD`).
> Поставь там тот же сильный пароль.

## 7. Запустить контейнеры

`docker-compose.override.yml` нужен только для локальной разработки — на проде
его быть не должно (иначе вебхук отключится). Удали его на сервере:

```bash
rm -f docker-compose.override.yml
docker compose up -d --build
docker compose logs -f bot     # смотрим логи, ищем "Bot starting up"
```

Миграции Alembic применяются автоматически (это прописано в `Dockerfile`:
`alembic upgrade head` перед стартом бота). Бот стартует в режиме long polling,
а вебхук-сервер Robokassa слушает порт `8080` внутри контейнера (только если
задан `WEBHOOK_HOST`).

> **Если только Stars** — разделы 8 и 9 можно пропустить: звёзды приходят
> через обычные апдейты бота, без вебхука.

## 8. HTTPS через nginx + Let's Encrypt (для Robokassa)

Robokassa шлёт ResultURL-уведомления только на HTTPS. Ставим nginx на хосте как
обратный прокси к порту 8080 контейнера.

```bash
apt install -y nginx certbot python3-certbot-nginx
```

Скопируй конфиг из репозитория и подставь домен:

```bash
cp nginx.conf /etc/nginx/sites-available/luna
sed -i 's/your-domain.com/ВАШ-ДОМЕН.ru/g' /etc/nginx/sites-available/luna
ln -s /etc/nginx/sites-available/luna /etc/nginx/sites-enabled/luna
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Выпусти сертификат (certbot сам пропишет 443 и редирект):

```bash
certbot --nginx -d ВАШ-ДОМЕН.ru
```

Проверка: `https://ВАШ-ДОМЕН.ru/robokassa/result` должен отвечать (на GET — 404
или 405, это нормально; ResultURL принимает POST).

## 9. Прописать ResultURL в Robokassa

1. Кабинет Robokassa → **Технические настройки**.
2. **Result URL**: `https://ВАШ-ДОМЕН.ru/robokassa/result`, метод **POST**.
3. Алгоритм расчёта хеша — **MD5**.
4. Сохрани и дождись, пока магазин активируют.

## 10. Боевая проверка

**Stars (работает сразу):**
1. В боте: «💎 Pro-подписка» → «⭐ Месяц — … Stars».
2. Подтверди оплату звёздами. Бот пришлёт «✨ Оплата прошла — добро пожаловать в Pro!».

**Robokassa:**
1. «💎 Pro-подписка» → «💳 Месяц картой» → «Оплатить».
2. Оплати картой (или в тестовом режиме `ROBOKASSA_TEST_MODE=True`).
3. После оплаты бот должен прислать «✨ Оплата прошла — добро пожаловать в Pro!».
4. Проверь в логах: `docker compose logs bot | grep "Payment processed"`.

---

## Обслуживание

| Задача | Команда |
|---|---|
| Логи бота | `docker compose logs -f bot` |
| Перезапуск | `docker compose restart bot` |
| Обновить код | `git pull && docker compose up -d --build` |
| Бэкап БД | `docker compose exec db pg_dump -U luna luna_db > backup.sql` |
| Статус | `docker compose ps` |

**Перед приёмом первых платежей картой убедись**, что в Robokassa магазин
активирован, подписан договор и `ROBOKASSA_TEST_MODE=False`. Telegram Stars
работают сразу, без активации.
