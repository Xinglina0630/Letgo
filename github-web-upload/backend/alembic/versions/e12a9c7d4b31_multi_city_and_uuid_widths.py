"""Support multi-city itinerary nodes and 36-character collaboration UUIDs.

Revision ID: e12a9c7d4b31
Revises: c4d92a7e5b10
"""

from alembic import op
import sqlalchemy as sa

revision = "e12a9c7d4b31"
down_revision = "c4d92a7e5b10"
branch_labels = None
depends_on = None


def _drop_fk_for(column: str, table: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table):
        if column in (fk.get("constrained_columns") or []) and fk.get("name"):
            op.drop_constraint(fk["name"], table, type_="foreignkey")


def upgrade() -> None:
    # MySQL does not allow changing the width of a constrained column until
    # its foreign key is temporarily removed.
    _drop_fk_for("owner_user_id", "custom_place_tags")
    _drop_fk_for("project_id", "travel_project_custom_tags")
    _drop_fk_for("shared_by_user_id", "travel_project_custom_tags")
    op.alter_column("custom_place_tags", "owner_user_id",
                    existing_type=sa.String(length=32), type_=sa.String(length=36),
                    existing_nullable=False)
    op.alter_column("travel_project_custom_tags", "project_id",
                    existing_type=sa.String(length=32), type_=sa.String(length=36),
                    existing_nullable=False)
    op.alter_column("travel_project_custom_tags", "shared_by_user_id",
                    existing_type=sa.String(length=32), type_=sa.String(length=36),
                    existing_nullable=False)
    op.create_foreign_key("fk_custom_tags_owner", "custom_place_tags", "users", ["owner_user_id"], ["id"])
    op.create_foreign_key("fk_project_custom_tags_project", "travel_project_custom_tags", "travel_projects", ["project_id"], ["id"])
    op.create_foreign_key("fk_project_custom_tags_sharer", "travel_project_custom_tags", "users", ["shared_by_user_id"], ["id"])
    op.add_column("itinerary_nodes", sa.Column("city_name", sa.String(length=100), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("itinerary_nodes", "city_name")
    _drop_fk_for("shared_by_user_id", "travel_project_custom_tags")
    _drop_fk_for("project_id", "travel_project_custom_tags")
    _drop_fk_for("owner_user_id", "custom_place_tags")
    op.alter_column("travel_project_custom_tags", "shared_by_user_id",
                    existing_type=sa.String(length=36), type_=sa.String(length=32),
                    existing_nullable=False)
    op.alter_column("travel_project_custom_tags", "project_id",
                    existing_type=sa.String(length=36), type_=sa.String(length=32),
                    existing_nullable=False)
    op.alter_column("custom_place_tags", "owner_user_id",
                    existing_type=sa.String(length=36), type_=sa.String(length=32),
                    existing_nullable=False)
    op.create_foreign_key("fk_custom_tags_owner", "custom_place_tags", "users", ["owner_user_id"], ["id"])
    op.create_foreign_key("fk_project_custom_tags_project", "travel_project_custom_tags", "travel_projects", ["project_id"], ["id"])
    op.create_foreign_key("fk_project_custom_tags_sharer", "travel_project_custom_tags", "users", ["shared_by_user_id"], ["id"])
