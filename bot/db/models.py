from datetime import date, datetime
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(128))
    birth_date: Mapped[date | None] = mapped_column(Date)
    zodiac_sign: Mapped[str | None] = mapped_column(String(32))
    is_pro: Mapped[bool] = mapped_column(Boolean, default=False)
    pro_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_spreads: Mapped[int] = mapped_column(Integer, default=0)
    luna_persona: Mapped[str] = mapped_column(String(16), default="young_moon")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # False = blocked the bot
    referred_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    referral_bonus_given: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Spread(Base):
    __tablename__ = "spreads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    spread_type: Mapped[str] = mapped_column(String(32))  # tarot_3|relations_5|year_12|past|birthday
    question: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(128), nullable=True)  # for "Luna remembers"
    cards_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    interpretation: Mapped[str] = mapped_column(Text)
    # "Луна помнит": follow-up 14 days after a question-spread
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    follow_up_sent: Mapped[bool] = mapped_column(Boolean, default=False)


class DailyLimit(Base):
    __tablename__ = "daily_limits"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_limits_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    date: Mapped[date] = mapped_column(Date)
    tarot_count: Mapped[int] = mapped_column(Integer, default=0)
    horoscope_count: Mapped[int] = mapped_column(Integer, default=0)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    amount: Mapped[int] = mapped_column(Integer)
    plan: Mapped[str] = mapped_column(String(16))  # 'month' | 'year' | 'pack'
    # Set to the row's own autoincrement id right after INSERT (collision-free InvId).
    # Nullable so the initial flush passes; multiple NULLs don't violate UNIQUE.
    robokassa_inv_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|paid|failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
