from datetime import date, datetime, timezone, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from bot.db.models import User, DailyLimit, Payment


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None = None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def update_user(session: AsyncSession, telegram_id: int, **kwargs) -> None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        for key, value in kwargs.items():
            setattr(user, key, value)
        await session.commit()


async def get_daily_limit(session: AsyncSession, user_id: int, today: date) -> DailyLimit:
    result = await session.execute(
        select(DailyLimit).where(and_(DailyLimit.user_id == user_id, DailyLimit.date == today))
    )
    limit = result.scalar_one_or_none()
    if not limit:
        limit = DailyLimit(user_id=user_id, date=today)
        session.add(limit)
        await session.commit()
        await session.refresh(limit)
    return limit


async def increment_tarot(session: AsyncSession, user_id: int, today: date) -> None:
    limit = await get_daily_limit(session, user_id, today)
    limit.tarot_count += 1
    await session.commit()


async def increment_horoscope(session: AsyncSession, user_id: int, today: date) -> None:
    limit = await get_daily_limit(session, user_id, today)
    limit.horoscope_count += 1
    await session.commit()


async def set_pro(session: AsyncSession, user_id: int, plan: str) -> None:
    """Activate or extend Pro subscription.

    If the user already has an active subscription, the new period is added
    on top of the current expiry date (not from now) so they don't lose days.
    """
    now = datetime.now(timezone.utc)
    days = {"year": 365, "month": 30, "referral": 7}.get(plan, 30)

    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()

    # Extend from existing expiry if still active, otherwise from now
    base = (
        user.pro_until
        if (user and user.pro_until and user.pro_until > now)
        else now
    )
    pro_until = base + timedelta(days=days)
    await update_user(session, user_id, is_pro=True, pro_until=pro_until)


async def create_payment(session: AsyncSession, user_id: int, amount: int, plan: str, inv_id: int) -> Payment:
    payment = Payment(user_id=user_id, amount=amount, plan=plan, robokassa_inv_id=inv_id)
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


async def add_extra_spreads(session: AsyncSession, user_id: int, count: int) -> None:
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.extra_spreads += count
        await session.commit()


async def use_extra_spread(session: AsyncSession, user_id: int) -> None:
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    if user and user.extra_spreads > 0:
        user.extra_spreads -= 1
        await session.commit()


async def apply_referral(session: AsyncSession, user_id: int, referrer_id: int) -> bool:
    """Store referrer and give 7-day Pro bonus to both users. Returns True if bonus applied."""
    # Mark referred_by on new user
    result = await session.execute(select(User).where(User.telegram_id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.referred_by or user.referral_bonus_given:
        return False

    user.referred_by = referrer_id
    user.referral_bonus_given = True
    await session.commit()

    # Give 7 days Pro to both
    for uid in (user_id, referrer_id):
        await set_pro(session, uid, "referral")  # set_pro handles extension

    return True


async def set_payment_status(session: AsyncSession, inv_id: int, status: str) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.robokassa_inv_id == inv_id))
    payment = result.scalar_one_or_none()
    if payment:
        payment.status = status
        await session.commit()
    return payment
