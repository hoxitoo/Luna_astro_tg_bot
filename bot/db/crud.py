import json
from datetime import date, datetime, timezone, timedelta
from sqlalchemy import select, update, and_, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession
from bot.db.models import User, DailyLimit, Payment, Spread

_MSK = timezone(timedelta(hours=3))


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


async def set_pro(session: AsyncSession, user_id: int, plan: str, days: int | None = None) -> None:
    """Activate or extend Pro subscription.

    If the user already has an active subscription, the new period is added
    on top of the current expiry date (not from now) so they don't lose days.
    `days` overrides the plan's default duration (used by /grant_pro).
    """
    now = datetime.now(timezone.utc)
    if days is None:
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


async def create_payment(session: AsyncSession, user_id: int, amount: int, plan: str) -> Payment:
    """Create a payment row; InvId = the row's own autoincrement id (collision-free)."""
    payment = Payment(user_id=user_id, amount=amount, plan=plan)
    session.add(payment)
    await session.flush()  # populates payment.id
    payment.robokassa_inv_id = payment.id
    await session.commit()
    await session.refresh(payment)
    return payment


async def get_payment_by_inv_id(session: AsyncSession, inv_id: int) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.robokassa_inv_id == inv_id))
    return result.scalar_one_or_none()


async def mark_payment_paid(session: AsyncSession, inv_id: int) -> Payment | None:
    """Atomic pending→paid transition. Returns the payment only on the FIRST call;
    a replayed/duplicate callback gets None and must not grant anything."""
    result = await session.execute(
        update(Payment)
        .where(Payment.robokassa_inv_id == inv_id, Payment.status == "pending")
        .values(status="paid")
        .returning(Payment)
    )
    payment = result.scalar_one_or_none()
    await session.commit()
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
    # The referrer must be a real existing user — otherwise /start ref_<any_number>
    # would mint a free Pro week for every fresh account
    ref_result = await session.execute(select(User).where(User.telegram_id == referrer_id))
    if ref_result.scalar_one_or_none() is None:
        return False

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


FOLLOW_UP_DAYS = 14


async def save_spread(
    session: AsyncSession,
    user_id: int,
    spread_type: str,
    interpretation: str,
    *,
    question: str | None = None,
    topic: str | None = None,
    cards_json: list | None = None,
) -> Spread:
    # "Луна помнит": spreads asked about a concrete situation get a follow-up
    follow_up = (
        datetime.now(_MSK).date() + timedelta(days=FOLLOW_UP_DAYS)
        if question
        else None
    )
    spread = Spread(
        user_id=user_id,
        spread_type=spread_type,
        interpretation=interpretation,
        question=question,
        topic=topic,
        cards_json=json.dumps(cards_json, ensure_ascii=False) if cards_json is not None else None,
        follow_up_date=follow_up,
    )
    session.add(spread)
    await session.commit()
    await session.refresh(spread)
    return spread


async def get_spreads_page(
    session: AsyncSession,
    user_id: int,
    page: int,
    per_page: int = 8,
) -> tuple[list[Spread], int]:
    count_result = await session.execute(
        select(sqlfunc.count()).select_from(Spread).where(Spread.user_id == user_id)
    )
    total = count_result.scalar_one()
    offset = (page - 1) * per_page
    result = await session.execute(
        select(Spread)
        .where(Spread.user_id == user_id)
        .order_by(Spread.created_at.desc())
        .limit(per_page)
        .offset(offset)
    )
    return result.scalars().all(), total


async def get_spread_by_id(session: AsyncSession, spread_id: int, user_id: int) -> Spread | None:
    result = await session.execute(
        select(Spread).where(Spread.id == spread_id, Spread.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_users_with_birthday_today(session: AsyncSession) -> list[User]:
    """Return active users whose birth_date month+day match today (MSK)."""
    today = datetime.now(_MSK).date()
    result = await session.execute(
        select(User).where(
            sqlfunc.extract("month", User.birth_date) == today.month,
            sqlfunc.extract("day", User.birth_date) == today.day,
            User.is_active.is_(True),
        )
    )
    return result.scalars().all()


async def get_due_follow_ups(session: AsyncSession) -> list[tuple[Spread, User]]:
    """Spreads whose follow-up is due (date <= today MSK, not yet sent), with their
    active owners. One per user — the most recent spread, so a backlog doesn't
    turn into день-за-днём spam."""
    today = datetime.now(_MSK).date()
    result = await session.execute(
        select(Spread, User)
        .join(User, User.telegram_id == Spread.user_id)
        .where(
            Spread.follow_up_date.is_not(None),
            Spread.follow_up_date <= today,
            Spread.follow_up_sent.is_(False),
            User.is_active.is_(True),
        )
        .order_by(Spread.user_id, Spread.created_at.desc())
    )
    rows = result.all()
    latest_per_user: dict[int, tuple[Spread, User]] = {}
    for spread, user in rows:
        latest_per_user.setdefault(user.telegram_id, (spread, user))
    return list(latest_per_user.values())


async def mark_follow_ups_sent(session: AsyncSession, user_id: int) -> None:
    """Mark ALL due follow-ups of this user as sent — we send only the latest one."""
    today = datetime.now(_MSK).date()
    await session.execute(
        update(Spread)
        .where(
            Spread.user_id == user_id,
            Spread.follow_up_date.is_not(None),
            Spread.follow_up_date <= today,
            Spread.follow_up_sent.is_(False),
        )
        .values(follow_up_sent=True)
    )
    await session.commit()


async def mark_users_inactive(session: AsyncSession, user_ids: list[int]) -> None:
    """Mark users who blocked the bot so broadcasts skip them."""
    if not user_ids:
        return
    await session.execute(
        update(User).where(User.telegram_id.in_(user_ids)).values(is_active=False)
    )
    await session.commit()


