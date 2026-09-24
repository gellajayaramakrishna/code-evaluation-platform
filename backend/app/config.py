from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Aether Judge"
    secret_key: str = "aether-dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    database_url: str = "sqlite:///./aether.db"
    redis_url: str = ""

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    sandbox_backend: str = "auto"
    docker_network: str = "aether_sandbox"
    worker_id: str = "worker-1"
    consumer_group: str = "judges"
    job_stream: str = "judge:jobs"
    priority_stream: str = "judge:jobs:priority"

    rate_limit: str = "30/minute"
    chromadb_path: str = "./chroma_data"

    cors_origins: str = "*"


settings = Settings()
