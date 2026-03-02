from fastapi import APIRouter, HTTPException, Query

from app.core.deps import DBSession
from app.schemas.evaluation import (
    EvaluationCompare,
    EvaluationCreate,
    EvaluationResponse,
    HumanRatingCreate,
    HumanRatingResponse,
)
from app.services.evaluation.eval_service import EvalService

router = APIRouter()


@router.post("", response_model=EvaluationResponse, status_code=201)
async def create_evaluation(payload: EvaluationCreate, db: DBSession):
    svc = EvalService(db)
    return await svc.create(payload)


@router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(evaluation_id: int, db: DBSession):
    svc = EvalService(db)
    ev = await svc.get(evaluation_id)
    if not ev:
        raise HTTPException(404, "Evaluation not found")
    return ev


@router.get("", response_model=list[EvaluationResponse])
async def list_evaluations(
    db: DBSession,
    training_run_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    svc = EvalService(db)
    return await svc.list_all(training_run_id=training_run_id, skip=skip, limit=limit)


@router.post("/compare")
async def compare_models(payload: EvaluationCompare, db: DBSession):
    svc = EvalService(db)
    return await svc.compare(payload)


@router.post("/ratings", response_model=HumanRatingResponse, status_code=201)
async def create_rating(payload: HumanRatingCreate, db: DBSession):
    svc = EvalService(db)
    return await svc.create_rating(payload)


@router.get("/ratings", response_model=list[HumanRatingResponse])
async def list_ratings(
    db: DBSession,
    inference_log_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    svc = EvalService(db)
    return await svc.list_ratings(inference_log_id=inference_log_id, skip=skip, limit=limit)
