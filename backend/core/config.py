"""
backend/core/config.py
======================
Centralised configuration using Pydantic Settings.
All values read from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────
    APP_NAME: str = "Telemedicine Workload Offloader API"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    ALLOWED_HOSTS: List[str] = ["*"]

    # ── Database (PostgreSQL) ─────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://telemedicine:telemedicine123@localhost:5432/telemedicine"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ─────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_CACHE_TTL: int = 300          # 5 minutes
    RATE_LIMIT_PER_MINUTE: int = 100

    # ── JWT Auth ──────────────────────────────────────────────────
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_openssl_rand_hex_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── MQTT ──────────────────────────────────────────────────────
    MQTT_HOST: str = "localhost"
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = "telemedicine/devices/#"
    MQTT_CLIENT_ID: str = "telemedicine-consumer"

    # ── Telegram Alerts ───────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_ENABLED: bool = False

    # ── Email Alerts ──────────────────────────────────────────────
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_USERNAME: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    EMAIL_ENABLED: bool = False
    DOCTOR_EMAIL: str = ""

    # ── RIPE Atlas ────────────────────────────────────────────────
    RIPE_API_KEY: str = ""

    # ── MLflow ────────────────────────────────────────────────────
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_NAME: str = "TelemedicineLatencyForecaster"

    # ── HIPAA / Security ──────────────────────────────────────────
    EMERGENCY_CRITICALITY_THRESHOLD: float = 9.0
    LATENCY_VETO_MS: float = 300.0
    BCRYPT_ROUNDS: int = 12

    # ── Prometheus ────────────────────────────────────────────────
    METRICS_ENABLED: bool = True

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def telegram_configured(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID)

    @property
    def email_configured(self) -> bool:
        return bool(self.EMAIL_USERNAME and self.EMAIL_PASSWORD)


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — created once per process."""
    return Settings()


settings = get_settings()
