"""Add source_tag_id to itinerary_nodes.

Revision ID: 3c2e844ffcc5
Revises: 0f1f7825dc00
Create Date: 2026-07-28
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '3c2e844ffcc5'
down_revision: Union[str, Sequence[str], None] = '0f1f7825dc00'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('itinerary_nodes') as b:
        b.add_column(sa.Column('source_tag_id', sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('itinerary_nodes') as b:
        b.drop_column('source_tag_id')
