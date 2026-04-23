"""add erp activity tracking table

Revision ID: 98a_erp_activity_tracking
Revises: 97a_erp_alerts_system
Create Date: 2026-04-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98a_erp_activity_tracking'
down_revision = '97a_erp_alerts_system'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'erp_user_activity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('last_activity', sa.DateTime(), nullable=False),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('device_info', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'workspace_id', name='uq_erp_user_activity_workspace_user'),
    )
    op.create_index('ix_erp_user_activity_user_id', 'erp_user_activity', ['user_id'], unique=False)
    op.create_index('ix_erp_user_activity_workspace_id', 'erp_user_activity', ['workspace_id'], unique=False)
    op.create_index('ix_erp_user_activity_last_activity', 'erp_user_activity', ['last_activity'], unique=False)
    op.create_index('ix_erp_user_activity_workspace_last_activity', 'erp_user_activity', ['workspace_id', 'last_activity'], unique=False)


def downgrade():
    op.drop_index('ix_erp_user_activity_workspace_last_activity', table_name='erp_user_activity')
    op.drop_index('ix_erp_user_activity_last_activity', table_name='erp_user_activity')
    op.drop_index('ix_erp_user_activity_workspace_id', table_name='erp_user_activity')
    op.drop_index('ix_erp_user_activity_user_id', table_name='erp_user_activity')
    op.drop_table('erp_user_activity')
