"""add_visual_uploads

Revision ID: 2f3d9f6c8a21
Revises: 47117de8ffa2
Create Date: 2026-05-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2f3d9f6c8a21"
down_revision: Union[str, Sequence[str], None] = "47117de8ffa2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visual_uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("call_id", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        sa.Column("analysis", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(op.f("ix_visual_uploads_id"), "visual_uploads", ["id"], unique=False)
    op.create_index(op.f("ix_visual_uploads_token"), "visual_uploads", ["token"], unique=False)
    op.create_index(op.f("ix_visual_uploads_call_id"), "visual_uploads", ["call_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_visual_uploads_call_id"), table_name="visual_uploads")
    op.drop_index(op.f("ix_visual_uploads_token"), table_name="visual_uploads")
    op.drop_index(op.f("ix_visual_uploads_id"), table_name="visual_uploads")
    op.drop_table("visual_uploads")

