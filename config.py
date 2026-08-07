from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    llm_provider: str = Field("stub")
    openai_api_key: str = Field(...)
    webhook_url: str = Field(...)
    ollama_host: str = Field("http://host.docker.internal:11434")
    db_path: str = Field("council.db")
    chroma_db_path: str = Field("chroma_db")
    fallback_provider: str = Field("stub")

# Instantiate and validate configuration immediately at boot time
settings = Settings()
