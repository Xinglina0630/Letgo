"""initial_schema_with_users

Revision ID: 96aa70aacbed
Revises:
Create Date: 2026-07-16 17:47:08.003681

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96aa70aacbed'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add users table and user_id foreign keys."""
    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=200), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    with op.batch_alter_table('flight_search_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_flight_search_sessions_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_flight_search_sessions_user_id',
            'users', ['user_id'], ['id'], ondelete='CASCADE'
        )

    with op.batch_alter_table('itineraries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_itineraries_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_itineraries_user_id',
            'users', ['user_id'], ['id'], ondelete='CASCADE'
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('itineraries', schema=None) as batch_op:
        batch_op.drop_constraint('fk_itineraries_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_itineraries_user_id'))
        batch_op.drop_column('user_id')

    with op.batch_alter_table('flight_search_sessions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_flight_search_sessions_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_flight_search_sessions_user_id'))
        batch_op.drop_column('user_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))

    op.drop_table('users')
