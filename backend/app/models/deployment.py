import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    STOPPED = "stopped"
    FAILED = "failed"


class ModelStage(str, enum.Enum):
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class DeployedModel(Base):
    __tablename__ = "deployed_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    training_run_id: Mapped[int] = mapped_column(
        ForeignKey("training_runs.id"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(DeploymentStatus), default=DeploymentStatus.PENDING
    )
    stage: Mapped[ModelStage] = mapped_column(Enum(ModelStage), default=ModelStage.STAGING)
    traffic_pct: Mapped[float] = mapped_column(Float, default=0.0)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
