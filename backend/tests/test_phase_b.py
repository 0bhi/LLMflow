from app.ml.evaluators.task_accuracy import TaskEvaluator
from app.models.inference import HumanRating, InferenceLog
from app.services.monitoring.monitor_service import MonitorService


class TestClassificationF1:
    def test_macro_f1_on_labels(self):
        ev = TaskEvaluator()
        results = ev.evaluate_classification(
            predictions=["pos", "neg", "pos"],
            references=["pos", "neg", "neg"],
        )
        assert results["n_samples"] == 3
        assert "f1_macro" in results
        assert 0 <= results["f1_macro"] <= 1
        assert results["accuracy"] == round(2 / 3, 4)


class TestErrorRateFromLogs:
    async def test_placeholder_counts_as_error(self, db):
        from app.models.dataset import Dataset, DatasetFormat, DatasetVersion
        from app.models.deployment import DeployedModel
        from app.models.training import Experiment, RunStatus, TrainingRun

        ds = Dataset(name="err-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()
        dv = DatasetVersion(
            dataset_id=ds.id, version=1, storage_path="p", content_hash="h", row_count=1
        )
        db.add(dv)
        await db.flush()
        exp = Experiment(
            name="err-exp",
            base_model="gpt2",
            dataset_version_id=dv.id,
            config_snapshot_json={},
        )
        db.add(exp)
        await db.flush()
        run = TrainingRun(
            experiment_id=exp.id,
            hyperparams={},
            seed=1,
            dataset_hash="h",
            config_hash="c",
            status=RunStatus.COMPLETED,
            model_artifact_path="m",
        )
        db.add(run)
        await db.flush()
        dep = DeployedModel(name="m", training_run_id=run.id, version="1", traffic_pct=100)
        db.add(dep)
        await db.flush()

        db.add(
            InferenceLog(
                deployed_model_id=dep.id,
                prompt_hash="a" * 64,
                prompt="hi",
                completion="ok",
                latency_ms=10,
                tokens_in=1,
                tokens_out=2,
            )
        )
        db.add(
            InferenceLog(
                deployed_model_id=dep.id,
                prompt_hash="b" * 64,
                prompt="hi",
                completion="[Model 'm' not loaded. This is a placeholder response.]",
                latency_ms=1,
                tokens_in=1,
                tokens_out=10,
            )
        )
        await db.flush()

        metrics = await MonitorService(db).get_metrics_summary(hours=24)
        assert metrics["total_requests"] == 2
        assert metrics["error_rate"] == 50.0


class TestQualityOverTime:
    async def test_groups_ratings_by_day(self, db):
        from app.models.dataset import Dataset, DatasetFormat, DatasetVersion
        from app.models.deployment import DeployedModel
        from app.models.training import Experiment, RunStatus, TrainingRun

        ds = Dataset(name="q-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()
        dv = DatasetVersion(
            dataset_id=ds.id, version=1, storage_path="p", content_hash="h", row_count=1
        )
        db.add(dv)
        await db.flush()
        exp = Experiment(
            name="q-exp",
            base_model="gpt2",
            dataset_version_id=dv.id,
            config_snapshot_json={},
        )
        db.add(exp)
        await db.flush()
        run = TrainingRun(
            experiment_id=exp.id,
            hyperparams={},
            seed=1,
            dataset_hash="h",
            config_hash="c",
            status=RunStatus.COMPLETED,
            model_artifact_path="m",
        )
        db.add(run)
        await db.flush()
        dep = DeployedModel(name="qm", training_run_id=run.id, version="1", traffic_pct=100)
        db.add(dep)
        await db.flush()
        log = InferenceLog(
            deployed_model_id=dep.id,
            prompt_hash="c" * 64,
            prompt="p",
            completion="c",
            latency_ms=5,
            tokens_in=1,
            tokens_out=1,
        )
        db.add(log)
        await db.flush()
        db.add(
            HumanRating(
                inference_log_id=log.id,
                rater_id="r",
                score=5,
                dimension="overall",
            )
        )
        await db.flush()

        quality = await MonitorService(db).get_quality_metrics(days=30)
        assert quality["total_ratings"] == 1
        assert quality["avg_human_score"] == 5.0
        assert len(quality["score_over_time"]) == 1


class TestEvalRatingsRoute:
    async def test_get_ratings_is_not_parsed_as_evaluation_id(self, db):
        from httpx import ASGITransport, AsyncClient

        from app.core.database import get_db
        from app.main import app

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/evaluations/ratings")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            app.dependency_overrides.clear()
