# Деплой Луны на VPS reg.ru

Пошаговая инструкция: от заказа сервера до бота, работающего 24/7 с приёмом
платежей ЮKassa.

---

## 0. Что понадобится

- Аккаунт на reg.ru
- Домен (можно купить там же — нужен для HTTPS-вебхука ЮKassa)
- Заполненные `BOT_TOKEN`, `CLAUDE_API_KEY`, `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`
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

# ЮKassa (ЛК → Интеграция → Ключи API)
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_секретный_ключ
YOOKASSA_RETURN_URL=https://t.me/luna_reads_bot

# Домен с HTTPS — включает приём вебхука ЮKassa
WEBHOOK_HOST=https://ваш-домен.ru

ADMIN_IDS=[1065395448]
BOT_USERNAME=luna_reads_bot
```

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
а вебхук-сервер ЮKassa слушает порт `8080` внутри контейнера.

## 8. HTTPS через nginx + Let's Encrypt

ЮKassa шлёт уведомления только на HTTPS. Ставим nginx на хосте как обратный
прокси к порту 8080 контейнера.

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

Проверка: `https://ВАШ-ДОМЕН.ru/yookassa/webhook` должен отвечать (на GET — 404
или 405, это нормально; вебхук принимает POST).

## 9. Прописать вебхук в ЮKassa

1. ЛК ЮKassa → **Интеграция** → **HTTP-уведомления**.
2. URL: `https://ВАШ-ДОМЕН.ru/yookassa/webhook`
3. Отметь событие **`payment.succeeded`**.
4. Сохрани.

## 10. Боевая проверка

1. В боте: «💎 Pro-подписка» → выбери план → «Оплатить».
2. Оплати реальной картой минимальной суммой (или используй
   [тестовые карты ЮKassa](https://yookassa.ru/developers/payment-acceptance/testing-and-going-live/testing),
   если магазин ещё в тестовом режиме).
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

**Перед приёмом первых платежей убедись**, что в ЮKassa магазин переведён из
тестового режима в боевой и подписан договор.
