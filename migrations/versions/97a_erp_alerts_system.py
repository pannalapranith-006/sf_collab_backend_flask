"""add erp alerts table

Revision ID: 97a_erp_alerts_system
Revises: 96a_erp_documents_system
Create Date: 2026-04-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '97a_erp_alerts_system'
down_revision = '96a_erp_documents_system'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'erp_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.Enum('missing_update', 'late_attendance', 'task_overdue', 'inactive_user', name='erp_alert_type_enum'), nullable=False),
        sa.Column('priority', sa.Enum('low', 'medium', 'high', name='erp_alert_priority_enum'), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('source_date', sa.Date(), nullable=False),
        sa.Column('dedupe_key', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dedupe_key'),
    )
    op.create_index('ix_erp_alerts_workspace_id', 'erp_alerts', ['workspace_id'], unique=False)
    op.create_index('ix_erp_alerts_user_id', 'erp_alerts', ['user_id'], unique=False)
    op.create_index('ix_erp_alerts_type', 'erp_alerts', ['type'], unique=False)
    op.create_index('ix_erp_alerts_resolved', 'erp_alerts', ['resolved'], unique=False)
    op.create_index('ix_erp_alerts_source_date', 'erp_alerts', ['source_date'], unique=False)
    op.create_index('ix_erp_alert_lookup', 'erp_alerts', ['workspace_id', 'type', 'source_date', 'resolved'], unique=False)


def downgrade():
    op.drop_index('ix_erp_alert_lookup', table_name='erp_alerts')
    op.drop_index('ix_erp_alerts_source_date', table_name='erp_alerts')
    op.drop_index('ix_erp_alerts_resolved', table_name='erp_alerts')
    op.drop_index('ix_erp_alerts_type', table_name='erp_alerts')
    op.drop_index('ix_erp_alerts_user_id', table_name='erp_alerts')
    op.drop_index('ix_erp_alerts_workspace_id', table_name='erp_alerts')
    op.drop_table('erp_alerts')
