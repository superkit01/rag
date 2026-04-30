from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260430_add_chunk_type_fields"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("chunk_type", sa.String(length=16), nullable=False, server_default="fixed"))
    op.add_column("chunks", sa.Column("parent_id", sa.String(length=64), nullable=True))
    op.create_index("ix_chunks_parent_id", "chunks", ["parent_id"])
    op.execute("UPDATE chunks SET chunk_type = 'fixed' WHERE chunk_type IS NULL OR chunk_type = ''")


def downgrade() -> None:
    op.drop_index("ix_chunks_parent_id", table_name="chunks")
    op.drop_column("chunks", "parent_id")
    op.drop_column("chunks", "chunk_type")
