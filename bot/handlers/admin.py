import asyncio
from datetime import datetime, timezone, timedelta
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from bot.config import settings
from bot.db.session import async_session_factory
from bot.db.models import User, Payment
from bot.db import crud

_BROADCAST_DELAY = 0.05  # seconds between messages (Telegram flood control)

router = Router()


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    async with async_session_factory() as session:
        total_users = (await session.execute(select(func.count()).select_from(User))).scalar()
        pro_users = (await session.execute(
            select(func.count()).select_from(User).where(User.is_pro.is_(True))
        )).scalar()

        now = datetime.now(timezone.utc)
        active_pro = (await session.execute(
            select(func.count()).select_from(User).where(
                User.is_pro.is_(True),
                User.pro_until > now
            )
        )).scalar()

        today_start = datetime.now(timezone(timedelta(hours=3))).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        new_today = (await session.execute(
            select(func.count()).select_from(User).where(User.created_at >= today_start)
        )).scalar()

        paid_total = (await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "paid")
        )).scalar() or 0

        paid_month = (await session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == "paid",
                Payment.created_at >= today_start.replace(day=1)
            )
        )).scalar() or 0

    text = (
        "📊 *Статистика Luna*\n\n"
        f"👤 Всего пользователей: `{total_users}`\n"
        f"✨ Pro подписчиков: `{active_pro}` (активных)\n"
        f"🆕 Новых сегодня: `{new_today}`\n\n"
        f"💰 Выручка всего: `{paid_total} ₽`\n"
        f"📅 Выручка за месяц: `{paid_month} ₽`\n"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot) -> None:
    if not _is_admin(message.from_user.id):
        return

    # Usage: /broadcast Текст сообщения
    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer("Использование: `/broadcast Текст сообщения`", parse_mode="Markdown")
        return

    async with async_session_factory() as session:
        result = await session.execute(select(User.telegram_id))
        user_ids = result.scalars().all()

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(_BROADCAST_DELAY)

    await message.answer(
        f"✅ Рассылка завершена\n\nОтправлено: `{sent}`\nОшибок: `{failed}`",
        parse_mode="Markdown"
    )


@router.message(Command("grant_pro"))
async def cmd_grant_pro(message: Message) -> None:
    """Usage: /grant_pro <user_id> [days]"""
    if not _is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: `/grant_pro <user_id> [days=30]`", parse_mode="Markdown")
        return

    try:
        target_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 30
    except ValueError:
        await message.answer("Неверный формат ID или количества дней.")
        return

    async with async_session_factory() as session:
        user = await crud.get_or_create_user(session, target_id)
        now = datetime.now(timezone.utc)
        await crud.update_user(
            session, target_id,
            is_pro=True,
            pro_until=now + timedelta(days=days)
        )

    await message.answer(
        f"✅ Pro выдан пользователю `{target_id}` на `{days}` дней.",
        parse_mode="Markdown"
    )
