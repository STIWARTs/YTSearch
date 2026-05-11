from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    youtube_api_key: str = ""
    cache_ttl_hours: int = 24  # How long scored results are cached (CACHE_TTL_HOURS env var)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
