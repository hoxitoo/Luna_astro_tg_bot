from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    CLAUDE_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    # ЮKassa (YooKassa). Self-employed (НПД) mode: receipts are auto-generated
    # by YooKassa in «Мой налог», so we don't send a receipt object.
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    # Where the user lands after paying. Empty → falls back to the bot deep link.
    YOOKASSA_RETURN_URL: str = ""
    FREE_SPREADS_PER_DAY: int = 3
    FREE_CHAT_PER_DAY: int = 10
    SUBSCRIPTION_PRICE_MONTH: int = 199
    SUBSCRIPTION_PRICE_YEAR: int = 990
    WEBHOOK_HOST: str = ""
    SENTRY_DSN: str = ""
    ADMIN_IDS: list[int] = []
    BOT_USERNAME: str = ""  # e.g. luna_tarot_bot — used for referral links


settings = Settings()
