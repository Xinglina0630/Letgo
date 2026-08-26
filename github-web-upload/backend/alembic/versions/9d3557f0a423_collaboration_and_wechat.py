"""Collaboration tables, WeChat login, and data privacy fields.

Revision ID: 9d3557f0a423
Revises: 96aa70aacbed
Create Date: 2026-07-17
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '9d3557f0a423'
down_revision: Union[str, Sequence[str], None] = '96aa70aacbed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- New tables ----

    op.create_table('travel_projects',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('owner_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('travel_projects') as b:
        b.create_index('ix_travel_projects_owner_id', ['owner_id'])
        b.create_index('ix_travel_projects_city', ['city'])
        b.create_foreign_key('fk_tp_owner', 'users', ['owner_id'], ['id'], ondelete='CASCADE')

    op.create_table('travel_project_members',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('can_invite', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_user'),
    )
    with op.batch_alter_table('travel_project_members') as b:
        b.create_index('ix_tpm_project_id', ['project_id'])
        b.create_index('ix_tpm_user_id', ['user_id'])
        b.create_foreign_key('fk_tpm_project', 'travel_projects', ['project_id'], ['id'], ondelete='CASCADE')
        b.create_foreign_key('fk_tpm_user', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    op.create_table('travel_project_invites',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('inviter_id', sa.String(36), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('scope', sa.String(20), nullable=True),
        sa.Column('can_invite', sa.Boolean(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('used_count', sa.Integer(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('travel_project_invites') as b:
        b.create_index('ix_travel_project_invites_project_id', ['project_id'])
        b.create_index('ix_travel_project_invites_token_hash', ['token_hash'], unique=True)
        b.create_foreign_key('fk_tpi_project', 'travel_projects', ['project_id'], ['id'], ondelete='CASCADE')
        b.create_foreign_key('fk_tpi_inviter', 'users', ['inviter_id'], ['id'], ondelete='CASCADE')

    op.create_table('travel_project_events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('actor_id', sa.String(36), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.String(36), nullable=True),
        sa.Column('base_version', sa.Integer(), nullable=True),
        sa.Column('new_version', sa.Integer(), nullable=True),
        sa.Column('summary', sa.String(500), nullable=True),
        sa.Column('change_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('travel_project_events') as b:
        b.create_index('ix_tpe_project_created', ['project_id', 'created_at'])
        b.create_foreign_key('fk_tpe_project', 'travel_projects', ['project_id'], ['id'], ondelete='CASCADE')
        b.create_foreign_key('fk_tpe_actor', 'users', ['actor_id'], ['id'], ondelete='SET NULL')

    # ---- Users: WeChat fields ----
    with op.batch_alter_table('users') as b:
        b.add_column(sa.Column('wechat_openid', sa.String(100), nullable=True))
        b.add_column(sa.Column('wechat_unionid', sa.String(100), nullable=True))
        b.add_column(sa.Column('wechat_display_name', sa.String(200), nullable=True))
        b.add_column(sa.Column('wechat_avatar_url', sa.String(500), nullable=True))
        b.add_column(sa.Column('auth_source', sa.String(20), nullable=True))
        b.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))
        b.create_unique_constraint('uq_users_wechat_openid', ['wechat_openid'])

    # ---- Itineraries: project_id + version ----
    with op.batch_alter_table('itineraries') as b:
        b.add_column(sa.Column('project_id', sa.String(36), nullable=True))
        b.add_column(sa.Column('version', sa.Integer(), nullable=True))
        b.create_index('ix_itineraries_project_id', ['project_id'])
        b.create_foreign_key('fk_itineraries_project', 'travel_projects', ['project_id'], ['id'], ondelete='SET NULL')

    # ---- FlightSearchSession: project_id ----
    with op.batch_alter_table('flight_search_sessions') as b:
        b.add_column(sa.Column('project_id', sa.String(36), nullable=True))
        b.create_index('ix_flight_search_sessions_project_id', ['project_id'])
        b.create_foreign_key('fk_fss_project', 'travel_projects', ['project_id'], ['id'], ondelete='SET NULL')

    # ---- PlatformFlightQuote: collaboration fields ----
    with op.batch_alter_table('platform_flight_quotes') as b:
        b.add_column(sa.Column('project_id', sa.String(36), nullable=True))
        b.add_column(sa.Column('created_by', sa.String(36), nullable=True))
        b.add_column(sa.Column('updated_by', sa.String(36), nullable=True))
        b.add_column(sa.Column('confirmed_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('version', sa.Integer(), nullable=True))
        b.create_index('ix_pfq_project_id', ['project_id'])
        b.create_foreign_key('fk_pfq_project', 'travel_projects', ['project_id'], ['id'], ondelete='SET NULL')
        b.create_foreign_key('fk_pfq_created_by', 'users', ['created_by'], ['id'], ondelete='SET NULL')
        b.create_foreign_key('fk_pfq_updated_by', 'users', ['updated_by'], ['id'], ondelete='SET NULL')

    # ---- ScreenshotImport: privacy fields ----
    with op.batch_alter_table('screenshot_imports') as b:
        b.add_column(sa.Column('project_id', sa.String(36), nullable=True))
        b.add_column(sa.Column('uploader_id', sa.String(36), nullable=True))
        b.add_column(sa.Column('private_visibility', sa.Boolean(), nullable=True))
        b.add_column(sa.Column('temporary_file_key', sa.String(200), nullable=True))
        b.add_column(sa.Column('parsed_draft', sa.Text(), nullable=True))
        b.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('file_deleted_at', sa.DateTime(), nullable=True))
        b.add_column(sa.Column('confirmed_at', sa.DateTime(), nullable=True))
        b.create_index('ix_si_project_id', ['project_id'])
        b.create_index('ix_si_uploader_id', ['uploader_id'])
        b.create_foreign_key('fk_si_project', 'travel_projects', ['project_id'], ['id'], ondelete='SET NULL')
        b.create_foreign_key('fk_si_uploader', 'users', ['uploader_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # Drop in reverse order
    tables_to_drop = ['travel_project_events', 'travel_project_invites',
                      'travel_project_members', 'travel_projects']
    for table in tables_to_drop:
        op.drop_table(table)

    with op.batch_alter_table('users') as b:
        b.drop_constraint('uq_users_wechat_openid', type_='unique')
        b.drop_column('last_login_at')
        b.drop_column('auth_source')
        b.drop_column('wechat_avatar_url')
        b.drop_column('wechat_display_name')
        b.drop_column('wechat_unionid')
        b.drop_column('wechat_openid')

    with op.batch_alter_table('itineraries') as b:
        b.drop_constraint('fk_itineraries_project', type_='foreignkey')
        b.drop_index('ix_itineraries_project_id')
        b.drop_column('version')
        b.drop_column('project_id')

    with op.batch_alter_table('flight_search_sessions') as b:
        b.drop_constraint('fk_fss_project', type_='foreignkey')
        b.drop_index('ix_flight_search_sessions_project_id')
        b.drop_column('project_id')

    with op.batch_alter_table('platform_flight_quotes') as b:
        b.drop_constraint('fk_pfq_updated_by', type_='foreignkey')
        b.drop_constraint('fk_pfq_created_by', type_='foreignkey')
        b.drop_constraint('fk_pfq_project', type_='foreignkey')
        b.drop_index('ix_pfq_project_id')
        b.drop_column('version')
        b.drop_column('confirmed_at')
        b.drop_column('updated_by')
        b.drop_column('created_by')
        b.drop_column('project_id')

    with op.batch_alter_table('screenshot_imports') as b:
        b.drop_constraint('fk_si_uploader', type_='foreignkey')
        b.drop_constraint('fk_si_project', type_='foreignkey')
        b.drop_index('ix_si_uploader_id')
        b.drop_index('ix_si_project_id')
        b.drop_column('confirmed_at')
        b.drop_column('file_deleted_at')
        b.drop_column('expires_at')
        b.drop_column('parsed_draft')
        b.drop_column('temporary_file_key')
        b.drop_column('private_visibility')
        b.drop_column('uploader_id')
        b.drop_column('project_id')
