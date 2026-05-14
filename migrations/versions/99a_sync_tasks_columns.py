"""sync tasks table columns with model

Revision ID: 99a_sync_tasks_columns
Revises: 98a_erp_activity_tracking
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99a_sync_tasks_columns'
down_revision = '98a_erp_activity_tracking'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('tasks')}

    if 'visible_by' not in columns:
        op.add_column(
            'tasks',
            sa.Column('visible_by', sa.String(length=50), nullable=True, server_default='all'),
        )

    if 'urgent' not in columns:
        op.add_column(
            'tasks',
            sa.Column('urgent', sa.Boolean(), nullable=True, server_default=sa.false()),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('tasks')}

    if 'urgent' in columns:
        op.drop_column('tasks', 'urgent')

    if 'visible_by' in columns:
        op.drop_column('tasks', 'visible_by')
