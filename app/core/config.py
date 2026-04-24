from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    ODDSPAPI_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "forbid"

settings = Settings()
