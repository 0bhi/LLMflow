from datetime import datetime

from pydantic import BaseModel

from app.models.evaluation import EvalStatus, EvalType


class EvaluationCreate(BaseModel):
    training_run_id: int
    eval_type: EvalType
    dataset_split_id: int


class EvaluationResponse(BaseModel):
    id: int
    training_run_id: int
    eval_type: EvalType
    dataset_split_id: int
    results_json: dict | None
    score: float | None
    status: EvalStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationCompare(BaseModel):
    run_id_a: int
    run_id_b: int
    eval_type: EvalType
    dataset_split_id: int


class HumanRatingCreate(BaseModel):
    inference_log_id: int
    rater_id: str
    score: float
    feedback: str | None = None
    dimension: str = "overall"


class HumanRatingResponse(BaseModel):
    id: int
    inference_log_id: int
    rater_id: str
    score: float
    feedback: str | None
    dimension: str
    created_at: datetime

    model_config = {"from_attributes": True}
