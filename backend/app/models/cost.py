import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResourceType(str, enum.Enum):
    TRAINING = "training"
    INFERENCE = "inference"


class CostRecord(Base):
    __tablename__ = "cost_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_type: Mapped[ResourceType] = mapped_column(Enum(ResourceType), nullable=False)
    reference_id: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_hours: Mapped[float] = mapped_column(Float, default=0.0)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
