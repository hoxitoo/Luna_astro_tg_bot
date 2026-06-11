import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiohttp import web
from bot.config import settings
from bot.handlers import start, tarot, astro, payment, free_chat, admin, profile, errors, media
from bot.middleware.throttling import ThrottlingMiddleware
from bot.db.session import engine
from bot.db.models import Base
from bot.scheduler import create_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def on_startup(**kwargs) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")


async def main() -> None:
    if settings.SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
        logger.info("Sentry initialized")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)

    # Middleware
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())

    dp.startup.register(on_startup)

    # Routers — order matters
    dp.include_router(errors.router)    # errors first — global catch
    dp.include_router(admin.router)     # admin commands bypass filters
    dp.include_router(profile.router)   # /help /profile /cancel
    dp.include_router(start.router)
    dp.include_router(tarot.router)
    dp.include_router(astro.router)
    dp.include_router(payment.router)
    dp.include_router(media.router)       # media before free_chat
    dp.include_router(free_chat.router)  # last — catches unhandled text

    # Robokassa webhook server
    if settings.WEBHOOK_HOST:
        app = web.Application()
        app.router.add_post("/robokassa/result", payment.robokassa_result_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        logger.info("Robokassa webhook server started on :8080")

    # Daily card-of-day scheduler
    scheduler = create_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started (card of day at 09:00 MSK)")

    logger.info("Starting bot (long polling)...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
