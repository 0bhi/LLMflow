from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import DatasetVersion
from app.models.deployment import DeployedModel, DeploymentStatus, ModelStage
from app.models.training import Experiment, TrainingRun
from app.schemas.serving import DeploymentCreate, DeploymentUpdate


class DeploymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: DeploymentCreate) -> DeployedModel:
        run = await self.db.get(TrainingRun, payload.training_run_id)
        if not run:
            raise ValueError("Training run not found")

        dep = DeployedModel(
            name=payload.name,
            training_run_id=payload.training_run_id,
            version=payload.version,
            endpoint=f"/inference/v1/models/{payload.name}",
            traffic_pct=payload.traffic_pct,
            config_json=payload.config_json,
            status=DeploymentStatus.PENDING,
        )
        self.db.add(dep)
        await self.db.flush()
        return dep

    async def get(self, deployment_id: int) -> DeployedModel | None:
        return await self.db.get(DeployedModel, deployment_id)

    async def list_all(self, skip: int = 0, limit: int = 20) -> Sequence[DeployedModel]:
        result = await self.db.execute(
            select(DeployedModel).offset(skip).limit(limit).order_by(DeployedModel.created_at.desc())
        )
        return result.scalars().all()

    async def update(self, deployment_id: int, payload: DeploymentUpdate) -> DeployedModel:
        dep = await self.get(deployment_id)
        if not dep:
            raise ValueError("Deployment not found")
        if payload.traffic_pct is not None:
            dep.traffic_pct = payload.traffic_pct
        if payload.status is not None:
            dep.status = payload.status
        if payload.stage is not None:
            dep.stage = payload.stage
        await self.db.flush()
        return dep

    async def delete(self, deployment_id: int) -> None:
        dep = await self.get(deployment_id)
        if dep:
            dep.status = DeploymentStatus.STOPPED
            await self.db.flush()

    async def get_lineage(self, deployment_id: int) -> dict:
        dep = await self.get(deployment_id)
        if not dep:
            raise ValueError("Deployment not found")

        run = await self.db.get(TrainingRun, dep.training_run_id)
        exp = await self.db.get(Experiment, run.experiment_id) if run else None
        dv = await self.db.get(DatasetVersion, exp.dataset_version_id) if exp else None

        return {
            "deployment": {
                "id": dep.id,
                "name": dep.name,
                "version": dep.version,
                "status": dep.status.value,
            },
            "model_artifact": {
                "path": run.model_artifact_path if run else None,
                "config_hash": run.config_hash if run else None,
                "dataset_hash": run.dataset_hash if run else None,
            },
            "training_run": {
                "id": run.id if run else None,
                "status": run.status.value if run else None,
                "seed": run.seed if run else None,
                "gpu_hours": run.gpu_hours if run else None,
                "gpu_cost_usd": run.gpu_cost_usd if run else None,
            },
            "experiment": {
                "id": exp.id if exp else None,
                "name": exp.name if exp else None,
                "base_model": exp.base_model if exp else None,
            },
            "dataset_version": {
                "id": dv.id if dv else None,
                "version": dv.version if dv else None,
                "content_hash": dv.content_hash if dv else None,
                "row_count": dv.row_count if dv else None,
            },
        }

    async def list_registry(
        self, stage: str | None = None, skip: int = 0, limit: int = 20
    ) -> Sequence[DeployedModel]:
        query = select(DeployedModel).offset(skip).limit(limit).order_by(DeployedModel.created_at.desc())
        if stage:
            query = query.where(DeployedModel.stage == ModelStage(stage))
        result = await self.db.execute(query)
        return result.scalars().all()
