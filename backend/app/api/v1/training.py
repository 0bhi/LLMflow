from fastapi import APIRouter, HTTPException, Query

from app.core.deps import DBSession
from app.schemas.training import (
    ExperimentCreate,
    ExperimentResponse,
    SweepConfig,
    TrainingRunCreate,
    TrainingRunResponse,
)
from app.services.training.experiment_service import ExperimentService

router = APIRouter()


@router.post("/experiments", response_model=ExperimentResponse, status_code=201)
async def create_experiment(payload: ExperimentCreate, db: DBSession):
    svc = ExperimentService(db)
    return await svc.create(payload)


@router.get("/experiments", response_model=list[ExperimentResponse])
async def list_experiments(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    svc = ExperimentService(db)
    return await svc.list_all(skip=skip, limit=limit)


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(experiment_id: int, db: DBSession):
    svc = ExperimentService(db)
    exp = await svc.get(experiment_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    return exp


@router.post(
    "/experiments/{experiment_id}/runs",
    response_model=TrainingRunResponse,
    status_code=201,
)
async def create_run(experiment_id: int, payload: TrainingRunCreate, db: DBSession):
    svc = ExperimentService(db)
    return await svc.create_run(experiment_id, payload)


@router.get("/experiments/{experiment_id}/runs", response_model=list[TrainingRunResponse])
async def list_runs(experiment_id: int, db: DBSession):
    svc = ExperimentService(db)
    return await svc.list_runs(experiment_id)


@router.post("/runs/{run_id}/rerun", response_model=TrainingRunResponse, status_code=201)
async def rerun(run_id: int, db: DBSession):
    svc = ExperimentService(db)
    return await svc.rerun(run_id)


@router.post("/sweep", response_model=list[TrainingRunResponse], status_code=201)
async def launch_sweep(
    experiment_id: int,
    config: SweepConfig,
    db: DBSession,
):
    svc = ExperimentService(db)
    try:
        return await svc.launch_sweep(experiment_id, config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
