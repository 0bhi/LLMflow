from fastapi import APIRouter, HTTPException, Query

from app.core.deps import DBSession
from app.schemas.serving import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentUpdate,
    InferenceLogCreate,
    InferenceLogResponse,
)
from app.services.serving.deployment_service import DeploymentService
from app.services.serving.inference_log_service import InferenceLogService

router = APIRouter()


@router.post("/deployments", response_model=DeploymentResponse, status_code=201)
async def create_deployment(payload: DeploymentCreate, db: DBSession):
    svc = DeploymentService(db)
    try:
        return await svc.create(payload)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/deployments", response_model=list[DeploymentResponse])
async def list_deployments(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    svc = DeploymentService(db)
    return await svc.list_all(skip=skip, limit=limit)


@router.get("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(deployment_id: int, db: DBSession):
    svc = DeploymentService(db)
    dep = await svc.get(deployment_id)
    if not dep:
        raise HTTPException(404, "Deployment not found")
    return dep


@router.patch("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def update_deployment(deployment_id: int, payload: DeploymentUpdate, db: DBSession):
    svc = DeploymentService(db)
    try:
        return await svc.update(deployment_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/deployments/{deployment_id}/reload", response_model=DeploymentResponse)
async def reload_deployment(deployment_id: int, db: DBSession):
    svc = DeploymentService(db)
    try:
        return await svc.reload(deployment_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/deployments/{deployment_id}", status_code=204)
async def delete_deployment(deployment_id: int, db: DBSession):
    svc = DeploymentService(db)
    await svc.delete(deployment_id)


@router.post("/inference-logs", response_model=InferenceLogResponse, status_code=201)
async def create_inference_log(payload: InferenceLogCreate, db: DBSession):
    svc = InferenceLogService(db)
    try:
        return await svc.record(payload)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/lineage/{deployment_id}")
async def get_lineage(deployment_id: int, db: DBSession):
    svc = DeploymentService(db)
    try:
        return await svc.get_lineage(deployment_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/registry", response_model=list[DeploymentResponse])
async def model_registry(
    db: DBSession,
    stage: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    svc = DeploymentService(db)
    return await svc.list_registry(stage=stage, skip=skip, limit=limit)
