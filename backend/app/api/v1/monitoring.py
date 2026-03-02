from fastapi import APIRouter, Query

from app.core.deps import DBSession
from app.schemas.monitoring import CostPerModel, CostSummary, MetricsSummary, QualityMetrics, TrainingRunCost
from app.services.monitoring.monitor_service import MonitorService
from app.services.cost.cost_service import CostService

router = APIRouter()


@router.get("/costs/summary", response_model=CostSummary)
async def cost_summary(
    db: DBSession,
    days: int = Query(30, ge=1, le=365),
):
    svc = CostService(db)
    return await svc.get_summary(days=days)


@router.get("/costs/by-model", response_model=list[CostPerModel])
async def cost_by_model(db: DBSession):
    svc = CostService(db)
    return await svc.get_cost_by_model()


@router.get("/costs/training/{run_id}", response_model=TrainingRunCost)
async def training_run_cost(run_id: int, db: DBSession):
    svc = CostService(db)
    return await svc.get_training_cost(run_id)


@router.get("/metrics/summary", response_model=MetricsSummary)
async def metrics_summary(
    db: DBSession,
    hours: int = Query(24, ge=1, le=168),
):
    svc = MonitorService(db)
    return await svc.get_metrics_summary(hours=hours)


@router.get("/quality", response_model=QualityMetrics)
async def quality_metrics(
    db: DBSession,
    days: int = Query(30, ge=1, le=365),
):
    svc = MonitorService(db)
    return await svc.get_quality_metrics(days=days)
