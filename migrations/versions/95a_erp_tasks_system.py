"""add erp tasks table

Revision ID: 95a_erp_tasks_system
Revises: 94a_daily_updates_system
Create Date: 2026-04-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95a_erp_tasks_system'
down_revision = '94a_daily_updates_system'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'erp_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('deadline', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('todo', 'in_progress', 'done', name='erp_task_status_enum'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_erp_tasks_workspace_id', 'erp_tasks', ['workspace_id'], unique=False)
    op.create_index('ix_erp_tasks_assigned_to', 'erp_tasks', ['assigned_to'], unique=False)
    op.create_index('ix_erp_tasks_deadline', 'erp_tasks', ['deadline'], unique=False)
    op.create_index('ix_erp_tasks_created_by', 'erp_tasks', ['created_by'], unique=False)


def downgrade():
    op.drop_index('ix_erp_tasks_created_by', table_name='erp_tasks')
    op.drop_index('ix_erp_tasks_deadline', table_name='erp_tasks')
    op.drop_index('ix_erp_tasks_assigned_to', table_name='erp_tasks')
    op.drop_index('ix_erp_tasks_workspace_id', table_name='erp_tasks')
    op.drop_table('erp_tasks')
