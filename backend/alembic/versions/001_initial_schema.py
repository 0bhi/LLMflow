"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-02-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "format",
            sa.Enum("CSV", "JSONL", "PARQUET", name="datasetformat"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=100), server_default="upload", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "cost_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "resource_type",
            sa.Enum("TRAINING", "INFERENCE", name="resourcetype"),
            nullable=False,
        ),
        sa.Column("reference_id", sa.Integer(), nullable=False),
        sa.Column("gpu_hours", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("cost_usd", sa.Float(), server_default="0.0", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("schema_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("stats_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dataset_splits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), nullable=False),
        sa.Column(
            "split_type",
            sa.Enum("TRAIN", "VAL", "TEST", name="splittype"),
            nullable=False,
        ),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_model", sa.String(length=255), nullable=False),
        sa.Column("dataset_version_id", sa.Integer(), nullable=False),
        sa.Column(
            "config_snapshot_json",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("CREATED", "RUNNING", "COMPLETED", "FAILED", name="experimentstatus"),
            server_default="CREATED",
            nullable=True,
        ),
        sa.Column("mlflow_experiment_id", sa.String(length=255), nullable=True),
        sa.Column("seed", sa.Integer(), server_default="42", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column(
            "hyperparams",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("metrics_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("model_artifact_path", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED",
                name="runstatus",
            ),
            server_default="QUEUED",
            nullable=True,
        ),
        sa.Column("seed", sa.Integer(), server_default="42", nullable=True),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column("gpu_hours", sa.Float(), nullable=True),
        sa.Column("gpu_cost_usd", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["experiment_id"], ["experiments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("training_run_id", sa.Integer(), nullable=False),
        sa.Column(
            "eval_type",
            sa.Enum(
                "PERPLEXITY", "TASK_ACCURACY", "CLASSIFICATION", "SELF_CONSISTENCY", "HUMAN",
                name="evaltype",
            ),
            nullable=False,
        ),
        sa.Column("dataset_split_id", sa.Integer(), nullable=False),
        sa.Column("results_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("QUEUED", "RUNNING", "COMPLETED", "FAILED", name="evalstatus"),
            server_default="QUEUED",
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["training_run_id"], ["training_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_split_id"], ["dataset_splits.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deployed_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("training_run_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACTIVE", "STOPPED", "FAILED", name="deploymentstatus"),
            server_default="PENDING",
            nullable=True,
        ),
        sa.Column(
            "stage",
            sa.Enum("STAGING", "PRODUCTION", "ARCHIVED", name="modelstage"),
            server_default="STAGING",
            nullable=True,
        ),
        sa.Column("traffic_pct", sa.Float(), server_default="0.0", nullable=True),
        sa.Column("config_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["training_run_id"], ["training_runs.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "inference_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deployed_model_id", sa.Integer(), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("completion", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), server_default="0.0", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["deployed_model_id"], ["deployed_models.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inference_logs_prompt_hash", "inference_logs", ["prompt_hash"])

    op.create_table(
        "human_ratings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("inference_log_id", sa.Integer(), nullable=False),
        sa.Column("rater_id", sa.String(length=255), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("dimension", sa.String(length=100), server_default="overall", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["inference_log_id"], ["inference_logs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("human_ratings")
    op.drop_index("ix_inference_logs_prompt_hash", table_name="inference_logs")
    op.drop_table("inference_logs")
    op.drop_table("deployed_models")
    op.drop_table("evaluations")
    op.drop_table("training_runs")
    op.drop_table("experiments")
    op.drop_table("dataset_splits")
    op.drop_table("dataset_versions")
    op.drop_table("cost_records")
    op.drop_table("datasets")

    for enum_name in [
        "datasetformat", "splittype", "experimentstatus", "runstatus",
        "evaltype", "evalstatus", "deploymentstatus", "modelstage",
        "resourcetype",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
