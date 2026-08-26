"""Backfill NULLs in itinerary_nodes and itineraries columns.

Revision ID: 6a30ec81370d
Revises: 3c2e844ffcc5
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '6a30ec81370d'
down_revision = '3c2e844ffcc5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE itinerary_nodes SET coordinate_system = 'GCJ02' WHERE coordinate_system IS NULL")
    op.execute("UPDATE itinerary_nodes SET amap_poi_id = '' WHERE amap_poi_id IS NULL")
    op.execute("UPDATE itinerary_nodes SET location_source = '' WHERE location_source IS NULL")
    op.execute("UPDATE itinerary_nodes SET location_verified = 0 WHERE location_verified IS NULL")
    op.execute("UPDATE itinerary_nodes SET source_tag_id = '' WHERE source_tag_id IS NULL")
    op.execute("UPDATE itinerary_nodes SET tags = '' WHERE tags IS NULL")
    op.execute("UPDATE itinerary_nodes SET opening_time = '' WHERE opening_time IS NULL")
    op.execute("UPDATE itinerary_nodes SET ticket_link = '' WHERE ticket_link IS NULL")
    op.execute("UPDATE itinerary_nodes SET latitude = 0.0 WHERE latitude IS NULL")
    op.execute("UPDATE itinerary_nodes SET longitude = 0.0 WHERE longitude IS NULL")
    op.execute("UPDATE itinerary_nodes SET custom_name = '' WHERE custom_name IS NULL")
    op.execute("UPDATE itinerary_nodes SET custom_address = '' WHERE custom_address IS NULL")
    op.execute("UPDATE itinerary_nodes SET notes = '' WHERE notes IS NULL")
    op.execute("UPDATE itineraries SET version = 1 WHERE version IS NULL")


def downgrade() -> None:
    op.execute("UPDATE itinerary_nodes SET coordinate_system = NULL")
    op.execute("UPDATE itinerary_nodes SET amap_poi_id = NULL")
    op.execute("UPDATE itinerary_nodes SET location_source = NULL")
    op.execute("UPDATE itinerary_nodes SET location_verified = NULL")
    op.execute("UPDATE itinerary_nodes SET source_tag_id = NULL")
    op.execute("UPDATE itinerary_nodes SET tags = NULL")
    op.execute("UPDATE itinerary_nodes SET opening_time = NULL")
    op.execute("UPDATE itinerary_nodes SET ticket_link = NULL")
    op.execute("UPDATE itinerary_nodes SET latitude = NULL")
    op.execute("UPDATE itinerary_nodes SET longitude = NULL")
    op.execute("UPDATE itineraries SET version = NULL")
