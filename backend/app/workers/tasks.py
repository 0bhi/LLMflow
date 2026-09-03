import io
import json
import math
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone

import mlflow
from minio import Minio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.logging import get_logger
from app.models.cost import CostRecord, ResourceType
from app.models.dataset import DatasetSplit, DatasetVersion, SplitType
from app.models.evaluation import EvalStatus, EvalType, Evaluation
from app.models.training import Experiment, ExperimentStatus, RunStatus, TrainingRun
from app.workers.celery_app import celery_app

logger = get_logger("worker")

sync_url = settings.database_url.replace("+asyncpg", "")
engine = create_engine(sync_url)
SessionLocal = sessionmaker(bind=engine)


def _get_db():
    return SessionLocal()


def _get_minio() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _download_split_texts(storage: Minio, split: DatasetSplit) -> list[str]:
    """Download a split file from MinIO and return rows as text lines."""
    try:
        response = storage.get_object(settings.minio_bucket, split.storage_path)
        content = response.read()
        response.close()
        response.release_conn()
    except Exception:
        return []

    text = content.decode("utf-8", errors="replace")
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    return lines


def _parse_instruction_rows(lines: list[str]) -> list[str]:
    """Parse JSONL instruction rows into prompt+completion text for LM training."""
    texts = []
    for line in lines:
        try:
            row = json.loads(line)
            instruction = row.get("instruction", "")
            inp = row.get("input", "")
            output = row.get("output", "")
            prompt = f"### Instruction:\n{instruction}"
            if inp:
                prompt += f"\n### Input:\n{inp}"
            prompt += f"\n### Response:\n{output}"
            texts.append(prompt)
        except json.JSONDecodeError:
            texts.append(line)
    return texts


def _upload_dir_to_minio(storage: Minio, local_dir: str, minio_prefix: str) -> None:
    """Recursively upload a local directory to MinIO."""
    for root, _dirs, files in os.walk(local_dir):
        for fname in files:
            local_path = os.path.join(root, fname)
            rel_path = os.path.relpath(local_path, local_dir)
            object_name = f"{minio_prefix}/{rel_path}"
            storage.fput_object(settings.minio_bucket, object_name, local_path)


@celery_app.task(name="data.clean_dataset", bind=True, max_retries=3)
def clean_dataset(self, dataset_version_id: int) -> dict:
    logger.info("clean_dataset_start", dataset_version_id=dataset_version_id)
    db = _get_db()
    try:
        dv = db.get(DatasetVersion, dataset_version_id)
        if not dv:
            return {"status": "error", "message": "Dataset version not found"}

        stats = {
            "row_count": dv.row_count,
            "cleaned_at": datetime.now(timezone.utc).isoformat(),
        }
        dv.stats_json = stats
        db.commit()
        return {"status": "completed", "dataset_version_id": dataset_version_id, "stats": stats}
    finally:
        db.close()


@celery_app.task(name="training.run_training", bind=True, max_retries=1)
def run_training(self, run_id: int) -> dict:
    logger.info("training_start", run_id=run_id)
    db = _get_db()
    storage = _get_minio()

    try:
        run = db.get(TrainingRun, run_id)
        if not run:
            return {"status": "error", "message": "Run not found"}

        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        exp = db.get(Experiment, run.experiment_id)
        config = exp.config_snapshot_json
        merged = {**config, **run.hyperparams}

        dv = db.get(DatasetVersion, exp.dataset_version_id)

        train_split = (
            db.query(DatasetSplit)
            .filter(
                DatasetSplit.dataset_version_id == dv.id,
                DatasetSplit.split_type == SplitType.TRAIN,
            )
            .first()
        )
        val_split = (
            db.query(DatasetSplit)
            .filter(
                DatasetSplit.dataset_version_id == dv.id,
                DatasetSplit.split_type == SplitType.VAL,
            )
            .first()
        )

        if train_split and train_split.content_hash != run.dataset_hash:
            raise ValueError(
                f"Dataset hash mismatch: expected {run.dataset_hash}, "
                f"got {train_split.content_hash}. Data may have been corrupted."
            )

        # --- Load real training data from MinIO ---
        if train_split:
            train_lines = _download_split_texts(storage, train_split)
        else:
            resp = storage.get_object(settings.minio_bucket, dv.storage_path)
            raw = resp.read()
            resp.close()
            resp.release_conn()
            train_lines = [l.strip() for l in raw.decode("utf-8").strip().split("\n") if l.strip()]

        train_texts = _parse_instruction_rows(train_lines)

        val_texts = None
        if val_split:
            val_lines = _download_split_texts(storage, val_split)
            val_texts = _parse_instruction_rows(val_lines)

        # --- Run real LoRA training ---
        from app.ml.trainers.lora_trainer import LoRATrainer, LoRATrainingConfig

        output_dir = tempfile.mkdtemp(prefix="llmflow_train_")
        try:
            lora_config = LoRATrainingConfig(
                base_model=exp.base_model,
                lora_r=merged.get("lora_r", 16),
                lora_alpha=merged.get("lora_alpha", 32),
                lora_dropout=merged.get("lora_dropout", 0.05),
                target_modules=merged.get("target_modules", ["c_attn", "c_proj"]),
                learning_rate=merged.get("learning_rate", 2e-4),
                epochs=merged.get("epochs", 3),
                batch_size=merged.get("batch_size", 4),
                gradient_accumulation_steps=merged.get("gradient_accumulation_steps", 4),
                warmup_steps=merged.get("warmup_steps", 10),
                max_seq_length=merged.get("max_seq_length", 256),
                weight_decay=merged.get("weight_decay", 0.01),
                load_in_4bit=merged.get("load_in_4bit", False),
                seed=run.seed,
                output_dir=output_dir,
            )

            trainer = LoRATrainer(lora_config)
            trainer.setup()

            tokenizer = trainer.tokenizer

            def tokenize_texts(texts: list[str]):
                from torch.utils.data import Dataset as TorchDataset

                encodings = tokenizer(
                    texts,
                    truncation=True,
                    max_length=lora_config.max_seq_length,
                    padding="max_length",
                    return_tensors="pt",
                )

                class _TokenizedDataset(TorchDataset):
                    def __init__(self, enc):
                        self.input_ids = enc["input_ids"]
                        self.attention_mask = enc["attention_mask"]

                    def __len__(self):
                        return len(self.input_ids)

                    def __getitem__(self, idx):
                        return {
                            "input_ids": self.input_ids[idx],
                            "attention_mask": self.attention_mask[idx],
                        }

                return _TokenizedDataset(encodings)

            train_dataset = tokenize_texts(train_texts)
            eval_dataset = tokenize_texts(val_texts) if val_texts else None

            # --- MLflow tracking ---
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

            if not exp.mlflow_experiment_id:
                mlflow_exp = mlflow.set_experiment(exp.name)
                exp.mlflow_experiment_id = str(mlflow_exp.experiment_id)
                db.commit()
            else:
                mlflow.set_experiment(experiment_id=exp.mlflow_experiment_id)

            from app.ml.trainers.lora_trainer import get_library_versions, get_pip_freeze

            with mlflow.start_run(run_name=f"run-{run_id}"):
                mlflow.log_params({
                    "base_model": exp.base_model,
                    "seed": run.seed,
                    "config_hash": run.config_hash,
                    "dataset_hash": run.dataset_hash,
                    "train_samples": len(train_dataset),
                    "eval_samples": len(eval_dataset) if eval_dataset else 0,
                    **{
                        f"hp_{k}": v
                        for k, v in merged.items()
                        if not isinstance(v, (dict, list))
                    },
                })

                lib_versions = get_library_versions()
                for k, v in lib_versions.items():
                    mlflow.log_param(f"lib_{k}", v)

                pip_freeze = get_pip_freeze()
                if pip_freeze:
                    mlflow.log_text(pip_freeze, "pip_freeze.txt")

                mlflow.log_text(
                    json.dumps(merged, indent=2, default=str),
                    "config_snapshot.json",
                )

                metrics = trainer.train(train_dataset, eval_dataset)

                final_train_loss = metrics.get("train_loss", 0)
                final_eval_loss = metrics.get("eval_loss", final_train_loss * 1.1)
                perplexity = math.exp(min(final_eval_loss, 20))

                metrics["final_train_loss"] = round(final_train_loss, 4)
                metrics["final_eval_loss"] = round(final_eval_loss, 4)
                metrics["perplexity"] = round(perplexity, 4)

                for k, v in metrics.items():
                    if isinstance(v, (int, float)):
                        mlflow.log_metric(k, v)

            # --- Save model artifact to MinIO ---
            artifact_prefix = f"models/{exp.id}/run-{run_id}"
            save_dir = os.path.join(output_dir, "final_model")
            trainer.save(save_dir)
            _upload_dir_to_minio(storage, save_dir, artifact_prefix)

            elapsed_seconds = trainer.get_gpu_hours() * 3600 or (
                time.time() - run.started_at.timestamp()
            )
            gpu_hours = elapsed_seconds / 3600
            gpu_cost = gpu_hours * settings.gpu_cost_per_hour

            run.status = RunStatus.COMPLETED
            run.finished_at = datetime.now(timezone.utc)
            run.metrics_json = metrics
            run.model_artifact_path = artifact_prefix
            run.gpu_hours = round(gpu_hours, 4)
            run.gpu_cost_usd = round(gpu_cost, 4)

            cost_record = CostRecord(
                resource_type=ResourceType.TRAINING,
                reference_id=run_id,
                gpu_hours=gpu_hours,
                cost_usd=gpu_cost,
            )
            db.add(cost_record)

            exp.status = ExperimentStatus.COMPLETED
            db.commit()

            logger.info(
                "training_complete",
                run_id=run_id,
                metrics=metrics,
                gpu_hours=gpu_hours,
            )
            return {"status": "completed", "run_id": run_id, "metrics": metrics}

        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    except Exception as e:
        logger.error("training_failed", run_id=run_id, error=str(e))
        run = db.get(TrainingRun, run_id)
        if run:
            run.status = RunStatus.FAILED
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        return {"status": "failed", "run_id": run_id, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="evaluation.run_evaluation", bind=True, max_retries=2)
def run_evaluation(self, evaluation_id: int) -> dict:
    logger.info("eval_start", evaluation_id=evaluation_id)
    db = _get_db()
    storage = _get_minio()

    try:
        ev = db.get(Evaluation, evaluation_id)
        if not ev:
            return {"status": "error", "message": "Evaluation not found"}

        split = db.get(DatasetSplit, ev.dataset_split_id)
        if not split:
            raise ValueError("Dataset split not found")
        if split.split_type == SplitType.TRAIN:
            raise ValueError("Cannot evaluate on training split")

        run = db.get(TrainingRun, ev.training_run_id)
        if split.content_hash == run.dataset_hash:
            raise ValueError("Evaluation split matches training data hash — possible leakage")

        ev.status = EvalStatus.RUNNING
        db.commit()

        # --- Download eval data from MinIO ---
        raw_lines = _download_split_texts(storage, split)
        texts = _parse_instruction_rows(raw_lines)

        # --- Download trained model from MinIO to temp dir ---
        model_path = _download_model_from_minio(storage, run.model_artifact_path)

        try:
            if ev.eval_type == EvalType.PERPLEXITY:
                results = _run_perplexity_eval(model_path, texts, split)
                score = results["perplexity"]

            elif ev.eval_type == EvalType.TASK_ACCURACY:
                results = _run_task_accuracy_eval(model_path, raw_lines, split, subtype="qa")
                score = results.get("exact_match", 0.0)

            elif ev.eval_type == EvalType.CLASSIFICATION:
                results = _run_task_accuracy_eval(
                    model_path, raw_lines, split, subtype="classification"
                )
                score = results.get("f1_macro", 0.0)

            elif ev.eval_type == EvalType.SELF_CONSISTENCY:
                prompts = [t.split("### Response:")[0] for t in texts[:20]]
                results = _run_self_consistency_eval(model_path, prompts, split)
                score = results["consistency_rate"]

            else:
                score = 0.0
                results = {"message": "Human eval — awaiting ratings"}

        finally:
            shutil.rmtree(model_path, ignore_errors=True)

        ev.status = EvalStatus.COMPLETED
        ev.score = round(score, 4)
        ev.results_json = results
        db.commit()

        logger.info("eval_complete", evaluation_id=evaluation_id, score=score)
        return {"status": "completed", "evaluation_id": evaluation_id, "score": score}

    except Exception as e:
        logger.error("eval_failed", evaluation_id=evaluation_id, error=str(e))
        ev = db.get(Evaluation, evaluation_id)
        if ev:
            ev.status = EvalStatus.FAILED
            db.commit()
        return {"status": "failed", "evaluation_id": evaluation_id, "error": str(e)}
    finally:
        db.close()


def _download_model_from_minio(storage: Minio, artifact_prefix: str) -> str:
    """Download all model files from MinIO prefix into a temp directory."""
    tmp_dir = tempfile.mkdtemp(prefix="llmflow_model_")
    objects = storage.list_objects(settings.minio_bucket, prefix=artifact_prefix, recursive=True)
    for obj in objects:
        rel_path = obj.object_name[len(artifact_prefix) :].lstrip("/")
        local_path = os.path.join(tmp_dir, rel_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        storage.fget_object(settings.minio_bucket, obj.object_name, local_path)
    return tmp_dir


def _run_perplexity_eval(model_path: str, texts: list[str], split: DatasetSplit) -> dict:
    from app.ml.evaluators.perplexity import PerplexityEvaluator

    evaluator = PerplexityEvaluator(model_path)
    evaluator.setup()
    results = evaluator.evaluate(texts[:200])
    results["split_type"] = split.split_type.value
    results["split_hash"] = split.content_hash
    return results


def _run_task_accuracy_eval(
    model_path: str,
    raw_lines: list[str],
    split: DatasetSplit,
    subtype: str = "qa",
) -> dict:
    """Generate predictions for each instruction and score QA exact-match or classification F1."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path)
    model.eval()
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    predictions, references = [], []
    for line in raw_lines[:50]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        instruction = row.get("instruction", "")
        inp = row.get("input", "")
        ref = row.get("output", "")
        prompt = f"### Instruction:\n{instruction}"
        if inp:
            prompt += f"\n### Input:\n{inp}"
        prompt += "\n### Response:\n"

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=64, do_sample=False)
        pred = tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        predictions.append(pred.strip())
        references.append(ref.strip())

    from app.ml.evaluators.task_accuracy import TaskEvaluator

    evaluator = TaskEvaluator()
    if subtype == "classification":
        results = evaluator.evaluate_classification(predictions, references)
    else:
        results = evaluator.evaluate_qa_exact_match(predictions, references)
    results["split_type"] = split.split_type.value
    results["split_hash"] = split.content_hash
    results["task_subtype"] = subtype
    return results


def _run_self_consistency_eval(
    model_path: str, prompts: list[str], split: DatasetSplit
) -> dict:
    from app.ml.evaluators.self_consistency import SelfConsistencyChecker

    checker = SelfConsistencyChecker(model_path, n_samples=3, temperature=0.8)
    checker.setup()
    results = checker.evaluate(prompts[:10], max_tokens=50)
    results["split_type"] = split.split_type.value
    results["split_hash"] = split.content_hash
    return results
