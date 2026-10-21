# config.py

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str = Field(min_length=32, repr=False)
    session_hours: int = 8
    app_env: str = "development"
    cors_origins: list[str] = Field(default_factory=list)
    db_pool_size: int = 5
    db_max_overflow: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.session_hours != 8:
            raise ValueError(
                "This release requires an eight-hour session lifetime"
            )

        if self.app_env.strip().lower() in {"production", "prod"}:
            secret = self.jwt_secret_key.strip()

            if (
                len(secret) < 32
                or "REPLACE_WITH" in secret.upper()
            ):
                raise ValueError(
                    "Production requires an independently generated JWT secret"
                )

            if not self.cors_origins:
                raise ValueError(
                    "Production requires explicit CORS_ORIGINS"
                )

            if "*" in self.cors_origins:
                raise ValueError(
                    "Wildcard CORS origins are not allowed in production"
                )

        return self


settings = Settings()
