"""Initial database schema creation

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create teams table
    op.create_table(
        'teams',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('constructor_code', sa.String(length=50), nullable=True),
        sa.Column('country', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('constructor_code')
    )

    # 2. Create drivers table
    op.create_table(
        'drivers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('driver_code', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('country', sa.String(length=50), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('driver_code')
    )

    # 3. Create races table
    op.create_table(
        'races',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('round', sa.Integer(), nullable=False),
        sa.Column('race_name', sa.String(length=100), nullable=False),
        sa.Column('circuit', sa.String(length=100), nullable=False),
        sa.Column('country', sa.String(length=50), nullable=True),
        sa.Column('race_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('season', 'round', name='uq_race_season_round')
    )

    # 4. Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('race_id', sa.Integer(), nullable=False),
        sa.Column('session_type', sa.String(length=20), nullable=False),
        sa.Column('session_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['race_id'], ['races.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 5. Create session_results table
    op.create_table(
        'session_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=True),
        sa.Column('lap_time', sa.Float(), nullable=True),
        sa.Column('sector_1', sa.Float(), nullable=True),
        sa.Column('sector_2', sa.Float(), nullable=True),
        sa.Column('sector_3', sa.Float(), nullable=True),
        sa.Column('tyre', sa.String(length=20), nullable=True),
        sa.Column('laps', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_results_driver_id'), 'session_results', ['driver_id'], unique=False)
    op.create_index(op.f('ix_session_results_session_id'), 'session_results', ['session_id'], unique=False)

    # 6. Create predictions table
    op.create_table(
        'predictions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('race_id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('prediction_stage', sa.String(length=30), nullable=False),
        sa.Column('predicted_position', sa.Integer(), nullable=True),
        sa.Column('win_probability', sa.Float(), nullable=True),
        sa.Column('podium_probability', sa.Float(), nullable=True),
        sa.Column('top5_probability', sa.Float(), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['race_id'], ['races.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_predictions_driver_id'), 'predictions', ['driver_id'], unique=False)
    op.create_index(op.f('ix_predictions_prediction_stage'), 'predictions', ['prediction_stage'], unique=False)
    op.create_index(op.f('ix_predictions_race_id'), 'predictions', ['race_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_predictions_race_id'), table_name='predictions')
    op.drop_index(op.f('ix_predictions_prediction_stage'), table_name='predictions')
    op.drop_index(op.f('ix_predictions_driver_id'), table_name='predictions')
    op.drop_table('predictions')

    op.drop_index(op.f('ix_session_results_session_id'), table_name='session_results')
    op.drop_index(op.f('ix_session_results_driver_id'), table_name='session_results')
    op.drop_table('session_results')

    op.drop_table('sessions')
    op.drop_table('races')
    op.drop_table('drivers')
    op.drop_table('teams')
