from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost import CostRecord, ResourceType
from app.models.deployment import DeployedModel
from app.models.inference import InferenceLog
from app.models.training import Experiment, TrainingRun


class CostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self, days: int = 30) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(
                CostRecord.resource_type,
                func.sum(CostRecord.cost_usd).label("total_cost"),
                func.sum(CostRecord.gpu_hours).label("total_gpu"),
                func.sum(CostRecord.token_count).label("total_tokens"),
            )
            .where(CostRecord.created_at >= since)
            .group_by(CostRecord.resource_type)
        )
        rows = result.all()

        training_cost = 0.0
        inference_cost = 0.0
        gpu_hours = 0.0
        tokens = 0

        for row in rows:
            if row.resource_type == ResourceType.TRAINING:
                training_cost = float(row.total_cost or 0)
                gpu_hours += float(row.total_gpu or 0)
            elif row.resource_type == ResourceType.INFERENCE:
                inference_cost = float(row.total_cost or 0)
                tokens += int(row.total_tokens or 0)

        return {
            "total_cost_usd": round(training_cost + inference_cost, 4),
            "training_cost_usd": round(training_cost, 4),
            "inference_cost_usd": round(inference_cost, 4),
            "total_gpu_hours": round(gpu_hours, 2),
            "total_tokens": tokens,
            "period_start": since.isoformat(),
            "period_end": now.isoformat(),
        }

    async def get_cost_by_model(self) -> list[dict]:
        result = await self.db.execute(
            select(
                DeployedModel.name,
                DeployedModel.id,
                func.count(InferenceLog.id).label("total_requests"),
                func.sum(InferenceLog.cost_usd).label("total_cost"),
                func.sum(InferenceLog.tokens_in + InferenceLog.tokens_out).label("total_tokens"),
            )
            .join(InferenceLog, InferenceLog.deployed_model_id == DeployedModel.id)
            .group_by(DeployedModel.id, DeployedModel.name)
        )
        rows = result.all()

        return [
            {
                "model_name": r.name,
                "deployment_id": r.id,
                "total_cost_usd": round(float(r.total_cost or 0), 4),
                "total_requests": int(r.total_requests or 0),
                "cost_per_1k_requests": round(
                    float(r.total_cost or 0) / max(int(r.total_requests or 0), 1) * 1000, 4
                ),
                "total_tokens": int(r.total_tokens or 0),
            }
            for r in rows
        ]

    async def get_training_cost(self, run_id: int) -> dict:
        run = await self.db.get(TrainingRun, run_id)
        if not run:
            raise ValueError(f"Training run {run_id} not found")

        exp = await self.db.get(Experiment, run.experiment_id)

        return {
            "run_id": run.id,
            "experiment_name": exp.name if exp else "unknown",
            "gpu_hours": run.gpu_hours or 0.0,
            "gpu_cost_usd": run.gpu_cost_usd or 0.0,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }
