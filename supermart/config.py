# config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
 
class Settings(BaseSettings):
    database_url: str
    session_hours: int = 8
    app_env: str = "development"
    cors_origins: list[str] = Field(default_factory=list)
    db_pool_size: int = 5
    db_max_overflow: int = 5
 
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
 
settings = Settings()
if settings.session_hours != 8:
    raise ValueError("This release requires a eight-hour session lifetime")

