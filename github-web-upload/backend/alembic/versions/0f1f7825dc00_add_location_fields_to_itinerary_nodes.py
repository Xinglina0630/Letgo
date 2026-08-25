"""Add location snapshot fields to itinerary_nodes.

Revision ID: 0f1f7825dc00
Revises: 9d3557f0a423
Create Date: 2026-07-28 18:37:11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0f1f7825dc00'
down_revision: Union[str, Sequence[str], None] = '9d3557f0a423'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('itinerary_nodes') as b:
        b.add_column(sa.Column('latitude', sa.Float(), nullable=True))
        b.add_column(sa.Column('longitude', sa.Float(), nullable=True))
        b.add_column(sa.Column('coordinate_system', sa.String(length=20), nullable=True))
        b.add_column(sa.Column('amap_poi_id', sa.String(length=100), nullable=True))
        b.add_column(sa.Column('location_source', sa.String(length=30), nullable=True))
        b.add_column(sa.Column('location_verified', sa.Boolean(), nullable=True))
        b.add_column(sa.Column('tags', sa.String(length=300), nullable=True))
        b.add_column(sa.Column('opening_time', sa.String(length=100), nullable=True))
        b.add_column(sa.Column('ticket_price', sa.Float(), nullable=True))
        b.add_column(sa.Column('ticket_link', sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('itinerary_nodes') as b:
        b.drop_column('ticket_link')
        b.drop_column('ticket_price')
        b.drop_column('opening_time')
        b.drop_column('tags')
        b.drop_column('location_verified')
        b.drop_column('location_source')
        b.drop_column('amap_poi_id')
        b.drop_column('coordinate_system')
        b.drop_column('longitude')
        b.drop_column('latitude')
