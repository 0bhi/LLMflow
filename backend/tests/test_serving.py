from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.cost import CostRecord, ResourceType
from app.models.dataset import Dataset, DatasetFormat, DatasetVersion
from app.models.deployment import DeploymentStatus
from app.models.inference import InferenceLog
from app.models.training import Experiment, RunStatus, TrainingRun
from app.schemas.serving import DeploymentCreate, InferenceLogCreate
from app.services.serving.deployment_service import DeploymentService
from app.services.serving.inference_log_service import InferenceLogService, compute_inference_cost


async def _completed_run(db) -> TrainingRun:
    ds = Dataset(name="serve-ds", format=DatasetFormat.JSONL)
    db.add(ds)
    await db.flush()
    dv = DatasetVersion(
        dataset_id=ds.id,
        version=1,
        storage_path="p",
        content_hash="abc",
        row_count=10,
    )
    db.add(dv)
    await db.flush()
    exp = Experiment(
        name="serve-exp",
        base_model="gpt2",
        dataset_version_id=dv.id,
        config_snapshot_json={"epochs": 1},
    )
    db.add(exp)
    await db.flush()
    run = TrainingRun(
        experiment_id=exp.id,
        hyperparams={},
        seed=42,
        dataset_hash="h",
        config_hash="c",
        status=RunStatus.COMPLETED,
        model_artifact_path="models/1/run-1",
    )
    db.add(run)
    await db.flush()
    return run


class TestDeploymentLoadsInference:
    async def test_create_loads_model_and_sets_active(self, db):
        run = await _completed_run(db)
        inference = MagicMock()
        inference.load_model = AsyncMock(return_value={"status": "loaded"})
        inference.set_route = AsyncMock()

        svc = DeploymentService(db, inference=inference)
        dep = await svc.create(
            DeploymentCreate(name="gpt2-demo", training_run_id=run.id, version="1.0.0", traffic_pct=100)
        )

        assert dep.status == DeploymentStatus.ACTIVE
        inference.load_model.assert_awaited_once()
        kwargs = inference.load_model.await_args.kwargs
        assert kwargs["model_name"] == "gpt2-demo"
        assert kwargs["artifact_path"] == "models/1/run-1"
        assert kwargs["traffic_pct"] == 100
        assert kwargs["deployed_model_id"] == dep.id

    async def test_create_rejects_run_without_artifact(self, db):
        run = await _completed_run(db)
        run.status = RunStatus.RUNNING
        run.model_artifact_path = None
        await db.flush()

        svc = DeploymentService(db, inference=MagicMock())
        with pytest.raises(ValueError, match="no completed model artifact"):
            await svc.create(
                DeploymentCreate(name="x", training_run_id=run.id, version="1.0.0", traffic_pct=50)
            )


class TestInferenceLogAndCost:
    async def test_record_writes_log_and_cost(self, db):
        run = await _completed_run(db)
        inference = MagicMock()
        inference.load_model = AsyncMock(return_value={"status": "loaded"})
        svc = DeploymentService(db, inference=inference)
        dep = await svc.create(
            DeploymentCreate(name="cost-model", training_run_id=run.id, version="1.0.0", traffic_pct=100)
        )

        logs = InferenceLogService(db)
        row = await logs.record(
            InferenceLogCreate(
                model_name="cost-model",
                prompt="hello",
                completion="world",
                tokens_in=10,
                tokens_out=20,
                latency_ms=12.5,
                deployed_model_id=dep.id,
            )
        )

        assert row.deployed_model_id == dep.id
        assert row.cost_usd == compute_inference_cost(10, 20)
        assert row.prompt_hash

        from sqlalchemy import select

        cost = (
            await db.execute(select(CostRecord).where(CostRecord.reference_id == row.id))
        ).scalar_one()
        assert cost.resource_type == ResourceType.INFERENCE
        assert cost.token_count == 30
        assert cost.cost_usd == row.cost_usd

        stored = await db.get(InferenceLog, row.id)
        assert stored.completion == "world"


class TestStopUnloadsModel:
    async def test_delete_unloads_and_zeros_traffic(self, db):
        run = await _completed_run(db)
        inference = MagicMock()
        inference.load_model = AsyncMock(return_value={"status": "loaded"})
        inference.unload_model = AsyncMock(return_value={"status": "unloaded"})
        inference.set_route = AsyncMock()

        svc = DeploymentService(db, inference=inference)
        dep = await svc.create(
            DeploymentCreate(name="unload-me", training_run_id=run.id, version="1.0.0", traffic_pct=80)
        )
        await svc.delete(dep.id)

        assert dep.status == DeploymentStatus.STOPPED
        assert dep.traffic_pct == 0.0
        inference.unload_model.assert_awaited_once_with("unload-me")


class TestRegistryStage:
    async def test_update_stage(self, db):
        from app.models.deployment import ModelStage
        from app.schemas.serving import DeploymentUpdate

        run = await _completed_run(db)
        inference = MagicMock()
        inference.load_model = AsyncMock(return_value={"status": "loaded"})
        svc = DeploymentService(db, inference=inference)
        dep = await svc.create(
            DeploymentCreate(name="staged", training_run_id=run.id, version="1.0.0", traffic_pct=100)
        )
        updated = await svc.update(dep.id, DeploymentUpdate(stage=ModelStage.PRODUCTION))
        assert updated.stage == ModelStage.PRODUCTION
