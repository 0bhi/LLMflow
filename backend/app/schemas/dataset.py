from datetime import datetime

from pydantic import BaseModel, Field

from app.models.dataset import DatasetFormat, SplitType


class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    format: DatasetFormat


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: str | None
    format: DatasetFormat
    source_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DatasetVersionResponse(BaseModel):
    id: int
    dataset_id: int
    version: int
    storage_path: str
    content_hash: str
    row_count: int
    schema_json: dict | None
    stats_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SplitConfig(BaseModel):
    train_ratio: float = Field(0.8, ge=0.0, le=1.0)
    val_ratio: float = Field(0.1, ge=0.0, le=1.0)
    test_ratio: float = Field(0.1, ge=0.0, le=1.0)
    stratify_column: str | None = None
    seed: int = 42


class DatasetSplitResponse(BaseModel):
    id: int
    dataset_version_id: int
    split_type: SplitType
    row_count: int
    storage_path: str
    content_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}
