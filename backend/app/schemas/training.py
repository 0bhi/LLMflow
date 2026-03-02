from datetime import datetime

from pydantic import BaseModel, Field

from app.models.training import ExperimentStatus, RunStatus


class ExperimentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    base_model: str = Field(..., min_length=1)
    dataset_version_id: int
    config_snapshot_json: dict
    seed: int = 42


class ExperimentResponse(BaseModel):
    id: int
    name: str
    base_model: str
    dataset_version_id: int
    config_snapshot_json: dict
    status: ExperimentStatus
    mlflow_experiment_id: str | None
    seed: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TrainingRunCreate(BaseModel):
    hyperparams: dict = Field(default_factory=dict)
    seed: int | None = None


class TrainingRunResponse(BaseModel):
    id: int
    experiment_id: int
    hyperparams: dict
    metrics_json: dict | None
    model_artifact_path: str | None
    status: RunStatus
    seed: int
    dataset_hash: str
    config_hash: str
    gpu_hours: float | None
    gpu_cost_usd: float | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class SweepConfig(BaseModel):
    strategy: str = Field("grid", pattern="^(grid|random)$")
    param_space: dict = Field(..., description="Parameter name -> list of values (grid) or distribution (random)")
    max_runs: int = Field(10, ge=1, le=100)
