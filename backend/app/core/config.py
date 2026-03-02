from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    project_name: str = "LLMflow"
    version: str = "0.1.0"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://llmflow:llmflow_dev_password@postgres:5432/llmflow"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "llmflow_minio"
    minio_secret_key: str = "llmflow_minio_secret"
    minio_bucket: str = "llmflow"
    minio_secure: bool = False

    mlflow_tracking_uri: str = "http://mlflow:5000"

    secret_key: str = "dev-secret-key-change-in-production"
    frontend_url: str = "http://localhost:3000"

    gpu_cost_per_hour: float = 2.50

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
