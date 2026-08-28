"""Add custom_place_tags and travel_project_custom_tags tables.

Revision ID: 7b1c8fa3d2e9
Revises: 6a30ec81370d
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7b1c8fa3d2e9'
down_revision = '6a30ec81370d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # custom_place_tags
    op.create_table(
        'custom_place_tags',
        sa.Column('id', sa.String(32), nullable=False),
        sa.Column('owner_user_id', sa.String(32), nullable=False),
        sa.Column('city', sa.String(64), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('place_type', sa.String(32), nullable=False, server_default='other'),
        sa.Column('address', sa.String(512), nullable=False, server_default=''),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('coordinate_system', sa.String(16), nullable=False, server_default='GCJ02'),
        sa.Column('amap_poi_id', sa.String(128), nullable=False, server_default=''),
        sa.Column('location_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('opening_time', sa.String(256), nullable=False, server_default=''),
        sa.Column('ticket_price', sa.Float(), nullable=True),
        sa.Column('official_url', sa.String(1024), nullable=False, server_default=''),
        sa.Column('status', sa.String(16), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    )
    op.create_index('idx_custom_tag_owner_city', 'custom_place_tags', ['owner_user_id', 'city'])
    op.create_index(op.f('ix_custom_place_tags_city'), 'custom_place_tags', ['city'])
    op.create_index(op.f('ix_custom_place_tags_owner_user_id'), 'custom_place_tags', ['owner_user_id'])

    # travel_project_custom_tags (junction table)
    op.create_table(
        'travel_project_custom_tags',
        sa.Column('id', sa.String(32), nullable=False),
        sa.Column('project_id', sa.String(32), nullable=False),
        sa.Column('custom_tag_id', sa.String(32), nullable=False),
        sa.Column('shared_by_user_id', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['travel_projects.id'], ),
        sa.ForeignKeyConstraint(['custom_tag_id'], ['custom_place_tags.id'], ),
        sa.ForeignKeyConstraint(['shared_by_user_id'], ['users.id'], ),
        sa.UniqueConstraint('project_id', 'custom_tag_id', name='uq_project_custom_tag'),
    )
    op.create_index(op.f('ix_travel_project_custom_tags_project_id'), 'travel_project_custom_tags', ['project_id'])
    op.create_index(op.f('ix_travel_project_custom_tags_custom_tag_id'), 'travel_project_custom_tags', ['custom_tag_id'])


def downgrade() -> None:
    op.drop_table('travel_project_custom_tags')
    op.drop_table('custom_place_tags')
