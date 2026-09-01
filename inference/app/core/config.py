from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "llmflow_minio"
    minio_secret_key: str = "llmflow_minio_secret"
    minio_bucket: str = "llmflow"
    minio_secure: bool = False

    backend_url: str = "http://backend:8000"
    redis_url: str = "redis://redis:6379/0"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
