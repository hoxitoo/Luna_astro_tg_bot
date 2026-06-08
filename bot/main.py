import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiohttp import web
from bot.config import settings
from bot.handlers import start, tarot, astro, payment, free_chat, admin
from bot.db.session import engine
from bot.db.models import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def on_startup(**kwargs) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")


async def main() -> None:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)

    dp.startup.register(on_startup)

    dp.include_router(admin.router)    # first — admin commands bypass all other filters
    dp.include_router(start.router)
    dp.include_router(tarot.router)
    dp.include_router(astro.router)
    dp.include_router(payment.router)
    dp.include_router(free_chat.router)  # last — catches unhandled text

    if settings.WEBHOOK_HOST:
        app = web.Application()
        app.router.add_post("/robokassa/result", payment.robokassa_result_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        logger.info("Robokassa webhook server started on :8080")

    logger.info("Starting bot (long polling)...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
