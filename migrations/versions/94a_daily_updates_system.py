"""add daily updates table

Revision ID: 94a_daily_updates_system
Revises: 93a_holiday_system
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '94a_daily_updates_system'
down_revision = '93a_holiday_system'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'daily_updates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('today_work', sa.Text(), nullable=False),
        sa.Column('next_plan', sa.Text(), nullable=False),
        sa.Column('blockers', sa.Text(), nullable=True),
        sa.Column('progress_rating', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'workspace_id', 'date', name='uq_daily_updates_user_workspace_date'),
    )
    op.create_index('ix_daily_updates_user_id', 'daily_updates', ['user_id'], unique=False)
    op.create_index('ix_daily_updates_workspace_id', 'daily_updates', ['workspace_id'], unique=False)
    op.create_index('ix_daily_updates_date', 'daily_updates', ['date'], unique=False)


def downgrade():
    op.drop_index('ix_daily_updates_date', table_name='daily_updates')
    op.drop_index('ix_daily_updates_workspace_id', table_name='daily_updates')
    op.drop_index('ix_daily_updates_user_id', table_name='daily_updates')
    op.drop_table('daily_updates')
