from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="MultiAI Research Assistant", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    api_key: SecretStr = Field(default=SecretStr("dev-secret-change-me"), alias="API_KEY")

    # LLM backend: "groq" or "ollama"
    llm_backend: str = Field(default="groq", alias="LLM_BACKEND")

    # Groq settings
    groq_api_key: SecretStr = Field(default=SecretStr(""), alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama3-8b-8192", alias="GROQ_MODEL")
    groq_model_fast: str = Field(default="llama3-8b-8192", alias="GROQ_MODEL_FAST")

    # Ollama settings (local dev fallback)
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.2:1b", alias="OLLAMA_MODEL")
    ollama_timeout: int = Field(default=120, alias="OLLAMA_TIMEOUT")
    ollama_num_predict_fast: int = Field(default=512, alias="OLLAMA_NUM_PREDICT_FAST")
    ollama_num_predict_report: int = Field(default=1400, alias="OLLAMA_NUM_PREDICT_REPORT")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_enabled: bool = Field(default=False, alias="REDIS_ENABLED")

    postgres_url: str = Field(
        default="postgresql+asyncpg://research:research@localhost:5432/research",
        alias="POSTGRES_URL",
    )
    postgres_enabled: bool = Field(default=False, alias="POSTGRES_ENABLED")

    max_subtasks: int = Field(default=4, alias="MAX_SUBTASKS")
    max_concurrent_research: int = Field(default=3, alias="MAX_CONCURRENT_RESEARCH")
    fast_pipeline: bool = Field(default=True, alias="FAST_PIPELINE")
    turbo_pipeline: bool = Field(default=False, alias="TURBO_PIPELINE")
    use_llm_planner: bool = Field(default=True, alias="USE_LLM_PLANNER")
    require_web_search: bool = Field(default=True, alias="REQUIRE_WEB_SEARCH")
    enable_verifier: bool = Field(default=True, alias="ENABLE_VERIFIER")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def using_groq(self) -> bool:
        return self.llm_backend.lower() == "groq"


@lru_cache
def get_settings() -> Settings:
    return Settings()
