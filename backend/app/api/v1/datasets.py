from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.core.deps import DBSession, StorageClient
from app.schemas.dataset import (
    DatasetCreate,
    DatasetResponse,
    DatasetSplitResponse,
    DatasetVersionResponse,
    SplitConfig,
)
from app.services.data.dataset_service import DatasetService

router = APIRouter()


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(payload: DatasetCreate, db: DBSession):
    svc = DatasetService(db)
    return await svc.create(payload)


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    db: DBSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    svc = DatasetService(db)
    return await svc.list_all(skip=skip, limit=limit)


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: int, db: DBSession):
    svc = DatasetService(db)
    ds = await svc.get(dataset_id)
    if not ds:
        raise HTTPException(404, "Dataset not found")
    return ds


@router.post("/{dataset_id}/upload", response_model=DatasetVersionResponse, status_code=201)
async def upload_dataset_version(
    dataset_id: int,
    db: DBSession,
    storage: StorageClient,
    file: UploadFile = File(...),
):
    svc = DatasetService(db, storage)
    try:
        return await svc.upload_version(dataset_id, file)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionResponse])
async def list_versions(dataset_id: int, db: DBSession):
    svc = DatasetService(db)
    return await svc.list_versions(dataset_id)


@router.post(
    "/{dataset_id}/versions/{version}/split",
    response_model=list[DatasetSplitResponse],
    status_code=201,
)
async def create_splits(
    dataset_id: int,
    version: int,
    config: SplitConfig,
    db: DBSession,
    storage: StorageClient,
):
    svc = DatasetService(db, storage)
    try:
        return await svc.create_splits(dataset_id, version, config)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get(
    "/{dataset_id}/versions/{version}/splits",
    response_model=list[DatasetSplitResponse],
)
async def get_splits(dataset_id: int, version: int, db: DBSession):
    svc = DatasetService(db)
    return await svc.get_splits(dataset_id, version)
