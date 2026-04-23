"""add attendance system table

Revision ID: 92a_attendance_system
Revises: 91a_workspace_foundation
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '92a_attendance_system'
down_revision = '91a_workspace_foundation'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'attendance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('clock_in_time', sa.DateTime(), nullable=True),
        sa.Column('clock_out_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', 'workspace_id', name='uq_attendance_user_date_workspace'),
    )
    op.create_index('ix_attendance_user_id', 'attendance', ['user_id'], unique=False)
    op.create_index('ix_attendance_workspace_id', 'attendance', ['workspace_id'], unique=False)
    op.create_index('ix_attendance_date', 'attendance', ['date'], unique=False)


def downgrade():
    op.drop_index('ix_attendance_date', table_name='attendance')
    op.drop_index('ix_attendance_workspace_id', table_name='attendance')
    op.drop_index('ix_attendance_user_id', table_name='attendance')
    op.drop_table('attendance')
