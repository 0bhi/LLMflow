from fastapi import APIRouter

from app.api.v1 import datasets, evaluations, monitoring, serving, training

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(training.router, prefix="/training", tags=["training"])
api_router.include_router(evaluations.router, prefix="/evaluations", tags=["evaluations"])
api_router.include_router(serving.router, prefix="/serving", tags=["serving"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
