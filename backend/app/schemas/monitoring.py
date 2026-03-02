from datetime import datetime

from pydantic import BaseModel


class CostSummary(BaseModel):
    total_cost_usd: float
    training_cost_usd: float
    inference_cost_usd: float
    total_gpu_hours: float
    total_tokens: int
    period_start: datetime
    period_end: datetime


class CostPerModel(BaseModel):
    model_name: str
    deployment_id: int
    total_cost_usd: float
    total_requests: int
    cost_per_1k_requests: float
    total_tokens: int


class TrainingRunCost(BaseModel):
    run_id: int
    experiment_name: str
    gpu_hours: float
    gpu_cost_usd: float
    started_at: datetime | None
    finished_at: datetime | None


class MetricsSummary(BaseModel):
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_requests: int
    error_rate: float
    tokens_per_second: float


class QualityMetrics(BaseModel):
    avg_human_score: float
    total_ratings: int
    score_by_dimension: dict[str, float]
