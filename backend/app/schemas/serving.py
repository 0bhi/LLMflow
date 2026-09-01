from datetime import datetime

from pydantic import BaseModel, Field

from app.models.deployment import DeploymentStatus, ModelStage


class DeploymentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    training_run_id: int
    version: str
    traffic_pct: float = Field(0.0, ge=0.0, le=100.0)
    config_json: dict | None = None


class DeploymentUpdate(BaseModel):
    traffic_pct: float | None = Field(None, ge=0.0, le=100.0)
    status: DeploymentStatus | None = None
    stage: ModelStage | None = None


class DeploymentResponse(BaseModel):
    id: int
    name: str
    training_run_id: int
    version: str
    endpoint: str | None
    status: DeploymentStatus
    stage: ModelStage
    traffic_pct: float
    config_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InferenceRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_tokens: int = Field(256, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    stream: bool = False


class InferenceResponse(BaseModel):
    completion: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    model_name: str
    cost_usd: float


class InferenceLogCreate(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_name: str
    prompt: str
    completion: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    deployed_model_id: int | None = None


class InferenceLogResponse(BaseModel):
    id: int
    deployed_model_id: int
    prompt_hash: str
    prompt: str
    completion: str
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost_usd: float
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
