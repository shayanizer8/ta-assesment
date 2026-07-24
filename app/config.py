import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/ta_assessment"
    )
    TEST_DATABASE_URL: str = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/ta_assessment_test"
    )
    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5433/ta_assessment"
    )
    SYNC_TEST_DATABASE_URL: str = os.getenv(
        "SYNC_TEST_DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5433/ta_assessment_test"
    )

    JWT_SECRET: str = os.getenv("JWT_SECRET", "ta_assessment_super_secret_jwt_key_2026_change_in_prod")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    RATE_LIMIT_CANDIDATE: str = "20/minute"
    RATE_LIMIT_AUTH: str = "5/minute"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
