"""sync idea_comments suggestion column

Revision ID: 100a_sync_idea_comments
Revises: 99a_sync_tasks_columns
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '100a_sync_idea_comments'
down_revision = '99a_sync_tasks_columns'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('idea_comments')}

    if 'suggestion' not in columns:
        op.add_column(
            'idea_comments',
            sa.Column('suggestion', sa.Boolean(), nullable=True, server_default=sa.false()),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('idea_comments')}

    if 'suggestion' in columns:
        op.drop_column('idea_comments', 'suggestion')
