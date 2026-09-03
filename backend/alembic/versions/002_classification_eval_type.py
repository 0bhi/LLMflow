"""add classification eval type

Revision ID: 002
Revises: 001
Create Date: 2026-09-01
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE evaltype ADD VALUE IF NOT EXISTS 'CLASSIFICATION'")


def downgrade() -> None:
    pass
