"""
Comprehensive tests for LLMflow core pipeline logic.
Tests data splitting, leakage detection, eval enforcement,
re-run cloning, upload hashing, and config dedup.
"""

import hashlib
import io
import json

import pytest
from unittest.mock import MagicMock

from app.models.dataset import Dataset, DatasetFormat, DatasetSplit, DatasetVersion, SplitType
from app.models.training import Experiment, ExperimentStatus, RunStatus, TrainingRun
from app.models.evaluation import Evaluation, EvalStatus, EvalType
from app.schemas.dataset import SplitConfig
from app.services.data.dataset_service import DatasetService


# ---------------------------------------------------------------------------
# 1. Splits sum to total rows
# ---------------------------------------------------------------------------

class TestSplitCounts:
    async def test_splits_sum_to_total_rows(self, db, mock_storage, sample_jsonl_content):
        """Train + val + test row counts must equal the original dataset row count."""
        ds = Dataset(name="test-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        content_hash = hashlib.sha256(sample_jsonl_content).hexdigest()
        dv = DatasetVersion(
            dataset_id=ds.id,
            version=1,
            storage_path="datasets/1/v1/data.jsonl",
            content_hash=content_hash,
            row_count=100,
        )
        db.add(dv)
        await db.flush()

        mock_storage._store["datasets/1/v1/data.jsonl"] = sample_jsonl_content

        svc = DatasetService(db, mock_storage)
        splits = await svc.create_splits(ds.id, 1, SplitConfig(
            train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=42,
        ))

        total_split_rows = sum(s.row_count for s in splits)
        assert total_split_rows == 100, (
            f"Splits sum to {total_split_rows}, expected 100"
        )

    async def test_splits_have_correct_types(self, db, mock_storage, sample_jsonl_content):
        ds = Dataset(name="test-ds-types", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="datasets/2/v1/data.jsonl",
            content_hash=hashlib.sha256(sample_jsonl_content).hexdigest(),
            row_count=100,
        )
        db.add(dv)
        await db.flush()

        mock_storage._store["datasets/2/v1/data.jsonl"] = sample_jsonl_content

        svc = DatasetService(db, mock_storage)
        splits = await svc.create_splits(ds.id, 1, SplitConfig(seed=42))

        split_types = {s.split_type for s in splits}
        assert split_types == {SplitType.TRAIN, SplitType.VAL, SplitType.TEST}


# ---------------------------------------------------------------------------
# 2. Leakage detection rejects overlapping splits
# ---------------------------------------------------------------------------

class TestLeakageDetection:
    def test_leakage_check_passes_for_disjoint_sets(self):
        hashes = {
            "train": {"a", "b", "c"},
            "val": {"d", "e"},
            "test": {"f", "g"},
        }
        DatasetService._check_leakage(hashes)

    def test_leakage_check_raises_on_overlap(self):
        hashes = {
            "train": {"a", "b", "c"},
            "val": {"c", "d"},
            "test": {"e"},
        }
        with pytest.raises(ValueError, match="Data leakage detected"):
            DatasetService._check_leakage(hashes)

    async def test_real_splits_have_no_leakage(self, db, mock_storage, sample_jsonl_content):
        """Actual split content hashes must be disjoint."""
        ds = Dataset(name="leak-test", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="datasets/3/v1/data.jsonl",
            content_hash=hashlib.sha256(sample_jsonl_content).hexdigest(),
            row_count=100,
        )
        db.add(dv)
        await db.flush()

        mock_storage._store["datasets/3/v1/data.jsonl"] = sample_jsonl_content

        svc = DatasetService(db, mock_storage)
        splits = await svc.create_splits(ds.id, 1, SplitConfig(seed=123))

        all_content_hashes = [s.content_hash for s in splits]
        assert len(all_content_hashes) == len(set(all_content_hashes)), (
            "Split content hashes must be unique"
        )


# ---------------------------------------------------------------------------
# 3. Eval API rejects train split
# ---------------------------------------------------------------------------

class TestEvalRejectsTrainSplit:
    async def test_eval_service_rejects_train_split(self, db):
        from app.services.evaluation.eval_service import EvalService
        from app.schemas.evaluation import EvaluationCreate

        ds = Dataset(name="eval-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="p", content_hash="abc", row_count=100,
        )
        db.add(dv)
        await db.flush()

        train_split = DatasetSplit(
            dataset_version_id=dv.id,
            split_type=SplitType.TRAIN,
            row_count=80, storage_path="s",
            content_hash="train_hash",
        )
        db.add(train_split)
        await db.flush()

        exp = Experiment(
            name="exp", base_model="gpt2",
            dataset_version_id=dv.id,
            config_snapshot_json={"epochs": 1},
        )
        db.add(exp)
        await db.flush()

        run = TrainingRun(
            experiment_id=exp.id,
            hyperparams={},
            seed=42,
            dataset_hash="train_hash",
            config_hash="ch",
        )
        db.add(run)
        await db.flush()

        svc = EvalService(db)
        with pytest.raises(ValueError, match="Cannot evaluate on training split"):
            await svc.create(EvaluationCreate(
                training_run_id=run.id,
                eval_type=EvalType.PERPLEXITY,
                dataset_split_id=train_split.id,
            ))


# ---------------------------------------------------------------------------
# 4. Re-run clones config correctly
# ---------------------------------------------------------------------------

class TestRerunClonesConfig:
    async def test_rerun_preserves_hyperparams_and_seed(self, db):
        from app.services.training.experiment_service import ExperimentService
        from unittest.mock import patch

        ds = Dataset(name="rerun-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="p", content_hash="abc", row_count=100,
        )
        db.add(dv)
        await db.flush()

        split = DatasetSplit(
            dataset_version_id=dv.id, split_type=SplitType.TRAIN,
            row_count=80, storage_path="s", content_hash="train_h",
        )
        db.add(split)
        await db.flush()

        exp = Experiment(
            name="rerun-exp", base_model="gpt2",
            dataset_version_id=dv.id,
            config_snapshot_json={"epochs": 1, "lora_r": 8},
        )
        db.add(exp)
        await db.flush()

        original = TrainingRun(
            experiment_id=exp.id,
            hyperparams={"learning_rate": 1e-4},
            seed=99,
            dataset_hash="train_h",
            config_hash="original_hash",
            status=RunStatus.COMPLETED,
        )
        db.add(original)
        await db.flush()

        svc = ExperimentService(db)

        with patch("app.services.training.experiment_service.run_training") as mock_task:
            mock_task.delay = MagicMock()
            new_run = await svc.rerun(original.id)

        assert new_run.hyperparams == original.hyperparams
        assert new_run.seed == original.seed
        assert new_run.config_hash == original.config_hash
        assert new_run.dataset_hash == original.dataset_hash
        assert new_run.id != original.id
        assert new_run.status == RunStatus.QUEUED


# ---------------------------------------------------------------------------
# 5. Dataset upload + hash computation
# ---------------------------------------------------------------------------

class TestDatasetUploadHash:
    async def test_upload_computes_sha256(self, db, mock_storage, sample_jsonl_content):
        ds = Dataset(name="hash-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        expected_hash = hashlib.sha256(sample_jsonl_content).hexdigest()

        from fastapi import UploadFile
        upload = UploadFile(
            filename="data.jsonl",
            file=io.BytesIO(sample_jsonl_content),
        )

        svc = DatasetService(db, mock_storage)
        version = await svc.upload_version(ds.id, upload)

        assert version.content_hash == expected_hash
        assert version.row_count == 100
        assert version.version == 1

    async def test_upload_increments_version(self, db, mock_storage, sample_jsonl_content):
        ds = Dataset(name="version-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        from fastapi import UploadFile

        svc = DatasetService(db, mock_storage)

        for expected_v in [1, 2, 3]:
            upload = UploadFile(
                filename="data.jsonl",
                file=io.BytesIO(sample_jsonl_content),
            )
            version = await svc.upload_version(ds.id, upload)
            assert version.version == expected_v


# ---------------------------------------------------------------------------
# 6. Training config hash dedup detection
# ---------------------------------------------------------------------------

class TestConfigHashDedup:
    async def test_duplicate_config_raises(self, db):
        from app.services.training.experiment_service import ExperimentService
        from app.schemas.training import TrainingRunCreate
        from unittest.mock import patch

        ds = Dataset(name="dedup-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="p", content_hash="abc", row_count=100,
        )
        db.add(dv)
        await db.flush()

        split = DatasetSplit(
            dataset_version_id=dv.id, split_type=SplitType.TRAIN,
            row_count=80, storage_path="s", content_hash="split_h",
        )
        db.add(split)
        await db.flush()

        config = {"epochs": 1, "lora_r": 16}
        exp = Experiment(
            name="dedup-exp", base_model="gpt2",
            dataset_version_id=dv.id,
            config_snapshot_json=config,
        )
        db.add(exp)
        await db.flush()

        svc = ExperimentService(db)
        hp = {"learning_rate": 2e-4}

        with patch("app.services.training.experiment_service.run_training") as mock_task:
            mock_task.delay = MagicMock()
            await svc.create_run(exp.id, TrainingRunCreate(hyperparams=hp))

        with pytest.raises(ValueError, match="identical config already exists"):
            with patch("app.services.training.experiment_service.run_training") as mock_task:
                mock_task.delay = MagicMock()
                await svc.create_run(exp.id, TrainingRunCreate(hyperparams=hp))


# ---------------------------------------------------------------------------
# 7. Split ratios must sum to 1.0
# ---------------------------------------------------------------------------

class TestSplitRatioValidation:
    async def test_bad_ratios_rejected(self, db, mock_storage, sample_jsonl_content):
        ds = Dataset(name="ratio-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="datasets/r/v1/data.jsonl",
            content_hash="x", row_count=100,
        )
        db.add(dv)
        await db.flush()

        svc = DatasetService(db, mock_storage)
        with pytest.raises(ValueError, match="Split ratios must sum to 1.0"):
            await svc.create_splits(ds.id, 1, SplitConfig(
                train_ratio=0.5, val_ratio=0.1, test_ratio=0.1,
            ))


# ---------------------------------------------------------------------------
# 8. Immutable splits — cannot re-split
# ---------------------------------------------------------------------------

class TestImmutableSplits:
    async def test_cannot_split_twice(self, db, mock_storage, sample_jsonl_content):
        ds = Dataset(name="immut-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="datasets/i/v1/data.jsonl",
            content_hash=hashlib.sha256(sample_jsonl_content).hexdigest(),
            row_count=100,
        )
        db.add(dv)
        await db.flush()

        mock_storage._store["datasets/i/v1/data.jsonl"] = sample_jsonl_content

        svc = DatasetService(db, mock_storage)
        await svc.create_splits(ds.id, 1, SplitConfig(seed=1))

        with pytest.raises(ValueError, match="Splits already exist"):
            await svc.create_splits(ds.id, 1, SplitConfig(seed=2))


# ---------------------------------------------------------------------------
# 9. Eval leakage check — hash match blocks eval
# ---------------------------------------------------------------------------

class TestEvalLeakageHashCheck:
    async def test_eval_rejects_matching_hash(self, db):
        from app.services.evaluation.eval_service import EvalService
        from app.schemas.evaluation import EvaluationCreate

        ds = Dataset(name="leak-eval-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="p", content_hash="x", row_count=100,
        )
        db.add(dv)
        await db.flush()

        val_split = DatasetSplit(
            dataset_version_id=dv.id,
            split_type=SplitType.VAL,
            row_count=10, storage_path="s",
            content_hash="SAME_HASH",
        )
        db.add(val_split)
        await db.flush()

        exp = Experiment(
            name="leak-exp", base_model="gpt2",
            dataset_version_id=dv.id,
            config_snapshot_json={},
        )
        db.add(exp)
        await db.flush()

        run = TrainingRun(
            experiment_id=exp.id, hyperparams={},
            seed=42, dataset_hash="SAME_HASH", config_hash="c",
        )
        db.add(run)
        await db.flush()

        svc = EvalService(db)
        with pytest.raises(ValueError, match="potential data leakage"):
            await svc.create(EvaluationCreate(
                training_run_id=run.id,
                eval_type=EvalType.PERPLEXITY,
                dataset_split_id=val_split.id,
            ))


# ---------------------------------------------------------------------------
# 10. Split files are actually stored in MinIO
# ---------------------------------------------------------------------------

class TestSplitFilesStored:
    async def test_split_files_written_to_storage(self, db, mock_storage, sample_jsonl_content):
        ds = Dataset(name="stored-ds", format=DatasetFormat.JSONL)
        db.add(ds)
        await db.flush()

        dv = DatasetVersion(
            dataset_id=ds.id, version=1,
            storage_path="datasets/s/v1/data.jsonl",
            content_hash=hashlib.sha256(sample_jsonl_content).hexdigest(),
            row_count=100,
        )
        db.add(dv)
        await db.flush()

        mock_storage._store["datasets/s/v1/data.jsonl"] = sample_jsonl_content

        svc = DatasetService(db, mock_storage)
        splits = await svc.create_splits(ds.id, 1, SplitConfig(seed=42))

        assert mock_storage.put_object.call_count == 3
        for split in splits:
            assert split.storage_path in mock_storage._store

            stored_content = mock_storage._store[split.storage_path]
            lines = [l for l in stored_content.decode().strip().split("\n") if l.strip()]
            assert len(lines) == split.row_count


# ---------------------------------------------------------------------------
# 11. Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    async def test_health_returns_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# 12. Row count utility
# ---------------------------------------------------------------------------

class TestRowCountParsing:
    def test_jsonl_count(self, sample_jsonl_content):
        count = DatasetService._count_rows(sample_jsonl_content, "jsonl")
        assert count == 100

    def test_csv_count(self):
        csv = b"col_a,col_b\n1,2\n3,4\n5,6\n"
        count = DatasetService._count_rows(csv, "csv")
        assert count == 3

    def test_empty_content(self):
        assert DatasetService._count_rows(b"", "jsonl") == 0
        assert DatasetService._count_rows(b"", "csv") == 0
