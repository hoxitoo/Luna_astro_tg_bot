from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    CLAUDE_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    ROBOKASSA_LOGIN: str = ""
    ROBOKASSA_PASSWORD1: str = ""
    ROBOKASSA_PASSWORD2: str = ""
    # Safe default: forgetting the env var in production must NOT silently serve test payments
    ROBOKASSA_TEST_MODE: bool = False
    FREE_SPREADS_PER_DAY: int = 3
    FREE_CHAT_PER_DAY: int = 10
    SUBSCRIPTION_PRICE_MONTH: int = 199
    SUBSCRIPTION_PRICE_YEAR: int = 990
    WEBHOOK_HOST: str = ""
    SENTRY_DSN: str = ""
    ADMIN_IDS: list[int] = []
    BOT_USERNAME: str = ""  # e.g. luna_tarot_bot — used for referral links


settings = Settings()
