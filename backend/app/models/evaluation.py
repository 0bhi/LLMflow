import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EvalStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvalType(str, enum.Enum):
    PERPLEXITY = "perplexity"
    TASK_ACCURACY = "task_accuracy"
    SELF_CONSISTENCY = "self_consistency"
    HUMAN = "human"


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    training_run_id: Mapped[int] = mapped_column(
        ForeignKey("training_runs.id", ondelete="CASCADE"), nullable=False
    )
    eval_type: Mapped[EvalType] = mapped_column(Enum(EvalType), nullable=False)
    dataset_split_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_splits.id"), nullable=False
    )
    results_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[EvalStatus] = mapped_column(Enum(EvalStatus), default=EvalStatus.QUEUED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
