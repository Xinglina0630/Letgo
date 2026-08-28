"""Add unique phone accounts and revocable login tokens.

Revision ID: f7a2c1d9e401
Revises: e12a9c7d4b31
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a2c1d9e401"
down_revision = "e12a9c7d4b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("phone", sa.String(length=20), nullable=True))
        b.add_column(sa.Column("password_updated_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
        b.create_index("ix_users_phone", ["phone"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.drop_index("ix_users_phone")
        b.drop_column("token_version")
        b.drop_column("password_updated_at")
        b.drop_column("phone")
