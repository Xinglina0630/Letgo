"""Add hashed room codes to collaboration invites.

Revision ID: a83d6e1f42c7
Revises: f7a2c1d9e401
"""
from alembic import op
import sqlalchemy as sa

revision = "a83d6e1f42c7"
down_revision = "f7a2c1d9e401"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("travel_project_invites") as b:
        b.add_column(sa.Column("code_hash", sa.String(length=64), nullable=True))
        b.create_index("ix_travel_project_invites_code_hash", ["code_hash"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("travel_project_invites") as b:
        b.drop_index("ix_travel_project_invites_code_hash")
        b.drop_column("code_hash")
