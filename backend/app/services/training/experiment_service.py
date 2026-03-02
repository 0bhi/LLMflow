import hashlib
import itertools
import json
import random
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import DatasetSplit, DatasetVersion, SplitType
from app.models.training import Experiment, ExperimentStatus, RunStatus, TrainingRun
from app.schemas.training import ExperimentCreate, SweepConfig, TrainingRunCreate
from app.workers.tasks import run_training


class ExperimentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: ExperimentCreate) -> Experiment:
        exp = Experiment(
            name=payload.name,
            base_model=payload.base_model,
            dataset_version_id=payload.dataset_version_id,
            config_snapshot_json=payload.config_snapshot_json,
            seed=payload.seed,
        )
        self.db.add(exp)
        await self.db.flush()
        return exp

    async def get(self, experiment_id: int) -> Experiment | None:
        return await self.db.get(Experiment, experiment_id)

    async def list_all(self, skip: int = 0, limit: int = 20) -> Sequence[Experiment]:
        result = await self.db.execute(
            select(Experiment).offset(skip).limit(limit).order_by(Experiment.created_at.desc())
        )
        return result.scalars().all()

    async def create_run(self, experiment_id: int, payload: TrainingRunCreate) -> TrainingRun:
        exp = await self.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        dv = await self.db.get(DatasetVersion, exp.dataset_version_id)
        if not dv:
            raise ValueError("Dataset version not found")

        train_split = await self.db.execute(
            select(DatasetSplit).where(
                DatasetSplit.dataset_version_id == dv.id,
                DatasetSplit.split_type == SplitType.TRAIN,
            )
        )
        split = train_split.scalar_one_or_none()
        dataset_hash = split.content_hash if split else dv.content_hash

        seed = payload.seed if payload.seed is not None else exp.seed
        merged_config = {**exp.config_snapshot_json, **payload.hyperparams}
        config_hash = hashlib.sha256(
            json.dumps(merged_config, sort_keys=True).encode()
        ).hexdigest()

        existing = await self.db.execute(
            select(TrainingRun).where(
                TrainingRun.experiment_id == experiment_id,
                TrainingRun.config_hash == config_hash,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(
                f"A run with identical config already exists (hash: {config_hash[:12]}...)"
            )

        run = TrainingRun(
            experiment_id=experiment_id,
            hyperparams=payload.hyperparams,
            status=RunStatus.QUEUED,
            seed=seed,
            dataset_hash=dataset_hash,
            config_hash=config_hash,
        )
        self.db.add(run)
        await self.db.flush()

        if exp.status == ExperimentStatus.CREATED:
            exp.status = ExperimentStatus.RUNNING
            await self.db.flush()

        run_training.delay(run.id)
        return run

    async def list_runs(self, experiment_id: int) -> Sequence[TrainingRun]:
        result = await self.db.execute(
            select(TrainingRun)
            .where(TrainingRun.experiment_id == experiment_id)
            .order_by(TrainingRun.id.desc())
        )
        return result.scalars().all()

    async def rerun(self, run_id: int) -> TrainingRun:
        original = await self.db.get(TrainingRun, run_id)
        if not original:
            raise ValueError(f"Training run {run_id} not found")

        new_run = TrainingRun(
            experiment_id=original.experiment_id,
            hyperparams=original.hyperparams,
            status=RunStatus.QUEUED,
            seed=original.seed,
            dataset_hash=original.dataset_hash,
            config_hash=original.config_hash,
        )
        self.db.add(new_run)
        await self.db.flush()

        run_training.delay(new_run.id)
        return new_run

    async def launch_sweep(
        self, experiment_id: int, config: SweepConfig
    ) -> list[TrainingRun]:
        exp = await self.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        param_combos: list[dict] = []
        if config.strategy == "grid":
            keys = list(config.param_space.keys())
            values = list(config.param_space.values())
            for combo in itertools.islice(itertools.product(*values), config.max_runs):
                param_combos.append(dict(zip(keys, combo)))
        else:
            for _ in range(config.max_runs):
                combo = {}
                for key, vals in config.param_space.items():
                    combo[key] = random.choice(vals)
                param_combos.append(combo)

        runs = []
        for params in param_combos:
            try:
                run = await self.create_run(
                    experiment_id, TrainingRunCreate(hyperparams=params)
                )
                runs.append(run)
            except ValueError:
                continue

        return runs
