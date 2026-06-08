from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    CLAUDE_API_KEY: str
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    ROBOKASSA_LOGIN: str = ""
    ROBOKASSA_PASSWORD1: str = ""
    ROBOKASSA_PASSWORD2: str = ""
    ROBOKASSA_TEST_MODE: bool = True
    FREE_SPREADS_PER_DAY: int = 3
    SUBSCRIPTION_PRICE_MONTH: int = 199
    SUBSCRIPTION_PRICE_YEAR: int = 990
    WEBHOOK_HOST: str = ""
    SENTRY_DSN: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
