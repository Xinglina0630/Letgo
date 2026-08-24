"""store avatars in database

Revision ID: c4d92a7e5b10
Revises: 7b1c8fa3d2e9
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c4d92a7e5b10"
down_revision: Union[str, Sequence[str], None] = "7b1c8fa3d2e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_content", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("avatar_content_type", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_content_type")
    op.drop_column("users", "avatar_content")
