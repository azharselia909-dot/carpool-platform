from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    jwt_private_key_path: str = "keys/private.pem"
    jwt_public_key_path: str = "keys/public.pem"
    jwt_issuer: str = "carpool-identity"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()