"""add holiday system table

Revision ID: 93a_holiday_system
Revises: 92a_attendance_system
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '93a_holiday_system'
down_revision = '92a_attendance_system'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'holidays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'date', name='uq_holiday_workspace_date'),
    )
    op.create_index('ix_holidays_workspace_id', 'holidays', ['workspace_id'], unique=False)
    op.create_index('ix_holidays_date', 'holidays', ['date'], unique=False)


def downgrade():
    op.drop_index('ix_holidays_date', table_name='holidays')
    op.drop_index('ix_holidays_workspace_id', table_name='holidays')
    op.drop_table('holidays')
