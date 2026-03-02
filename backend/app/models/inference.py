from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InferenceLog(Base):
    __tablename__ = "inference_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deployed_model_id: Mapped[int] = mapped_column(
        ForeignKey("deployed_models.id"), nullable=False
    )
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    completion: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HumanRating(Base):
    __tablename__ = "human_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inference_log_id: Mapped[int] = mapped_column(
        ForeignKey("inference_logs.id", ondelete="CASCADE"), nullable=False
    )
    rater_id: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimension: Mapped[str] = mapped_column(String(100), default="overall")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
