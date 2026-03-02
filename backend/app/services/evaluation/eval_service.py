from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dataset import DatasetSplit, SplitType
from app.models.evaluation import EvalStatus, Evaluation
from app.models.inference import HumanRating
from app.models.training import TrainingRun
from app.schemas.evaluation import EvaluationCompare, EvaluationCreate, HumanRatingCreate
from app.workers.tasks import run_evaluation


class EvalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, payload: EvaluationCreate) -> Evaluation:
        split = await self.db.get(DatasetSplit, payload.dataset_split_id)
        if not split:
            raise ValueError("Dataset split not found")
        if split.split_type == SplitType.TRAIN:
            raise ValueError("Cannot evaluate on training split. Use val or test.")

        training_run = await self.db.get(TrainingRun, payload.training_run_id)
        if not training_run:
            raise ValueError("Training run not found")

        if split.content_hash == training_run.dataset_hash:
            raise ValueError(
                "Evaluation split hash matches training data hash — potential data leakage."
            )

        ev = Evaluation(
            training_run_id=payload.training_run_id,
            eval_type=payload.eval_type,
            dataset_split_id=payload.dataset_split_id,
            status=EvalStatus.QUEUED,
        )
        self.db.add(ev)
        await self.db.flush()

        run_evaluation.delay(ev.id)
        return ev

    async def get(self, evaluation_id: int) -> Evaluation | None:
        return await self.db.get(Evaluation, evaluation_id)

    async def list_all(
        self,
        training_run_id: int | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[Evaluation]:
        query = select(Evaluation).offset(skip).limit(limit).order_by(Evaluation.created_at.desc())
        if training_run_id:
            query = query.where(Evaluation.training_run_id == training_run_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def compare(self, payload: EvaluationCompare) -> dict:
        result_a = await self.db.execute(
            select(Evaluation).where(
                Evaluation.training_run_id == payload.run_id_a,
                Evaluation.eval_type == payload.eval_type,
                Evaluation.dataset_split_id == payload.dataset_split_id,
            )
        )
        result_b = await self.db.execute(
            select(Evaluation).where(
                Evaluation.training_run_id == payload.run_id_b,
                Evaluation.eval_type == payload.eval_type,
                Evaluation.dataset_split_id == payload.dataset_split_id,
            )
        )
        eval_a = result_a.scalar_one_or_none()
        eval_b = result_b.scalar_one_or_none()

        return {
            "run_a": {
                "run_id": payload.run_id_a,
                "score": eval_a.score if eval_a else None,
                "results": eval_a.results_json if eval_a else None,
            },
            "run_b": {
                "run_id": payload.run_id_b,
                "score": eval_b.score if eval_b else None,
                "results": eval_b.results_json if eval_b else None,
            },
        }

    async def create_rating(self, payload: HumanRatingCreate) -> HumanRating:
        rating = HumanRating(
            inference_log_id=payload.inference_log_id,
            rater_id=payload.rater_id,
            score=payload.score,
            feedback=payload.feedback,
            dimension=payload.dimension,
        )
        self.db.add(rating)
        await self.db.flush()
        return rating

    async def list_ratings(
        self,
        inference_log_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[HumanRating]:
        query = select(HumanRating).offset(skip).limit(limit).order_by(HumanRating.created_at.desc())
        if inference_log_id:
            query = query.where(HumanRating.inference_log_id == inference_log_id)
        result = await self.db.execute(query)
        return result.scalars().all()
