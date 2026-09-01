from collections.abc import Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import DatasetVersion
from app.models.deployment import DeployedModel, DeploymentStatus, ModelStage
from app.models.training import Experiment, RunStatus, TrainingRun
from app.schemas.serving import DeploymentCreate, DeploymentUpdate
from app.services.serving.inference_client import InferenceClient


class DeploymentService:
    def __init__(self, db: AsyncSession, inference: InferenceClient | None = None):
        self.db = db
        self.inference = inference or InferenceClient()

    async def create(self, payload: DeploymentCreate) -> DeployedModel:
        run = await self.db.get(TrainingRun, payload.training_run_id)
        if not run:
            raise ValueError("Training run not found")
        if run.status != RunStatus.COMPLETED or not run.model_artifact_path:
            raise ValueError("Training run has no completed model artifact")

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

        await self._push_to_inference(dep, run)
        return dep

    async def _push_to_inference(self, dep: DeployedModel, run: TrainingRun | None = None) -> DeployedModel:
        if run is None:
            run = await self.db.get(TrainingRun, dep.training_run_id)
        if not run or not run.model_artifact_path:
            raise ValueError("Training run has no completed model artifact")
        try:
            await self.inference.load_model(
                model_name=dep.name,
                artifact_path=run.model_artifact_path,
                traffic_pct=dep.traffic_pct or 100.0,
                deployed_model_id=dep.id,
            )
            dep.status = DeploymentStatus.ACTIVE
        except (httpx.HTTPError, httpx.RequestError) as e:
            dep.status = DeploymentStatus.FAILED
            raise ValueError(f"Inference server failed to load model: {e}") from e
        await self.db.flush()
        return dep

    async def reload(self, deployment_id: int) -> DeployedModel:
        dep = await self.get(deployment_id)
        if not dep:
            raise ValueError("Deployment not found")
        return await self._push_to_inference(dep)

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
            try:
                await self.inference.set_route(dep.name, payload.traffic_pct)
            except (httpx.HTTPError, httpx.RequestError) as e:
                raise ValueError(f"Failed to update inference route: {e}") from e
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
            try:
                await self.inference.set_route(dep.name, 0.0)
            except (httpx.HTTPError, httpx.RequestError):
                pass
            dep.traffic_pct = 0.0
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
