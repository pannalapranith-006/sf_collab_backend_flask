"""add erp documents table

Revision ID: 96a_erp_documents_system
Revises: 95a_erp_tasks_system
Create Date: 2026-04-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '96a_erp_documents_system'
down_revision = '95a_erp_tasks_system'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'erp_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('folder', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=120), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_erp_documents_workspace_id', 'erp_documents', ['workspace_id'], unique=False)
    op.create_index('ix_erp_documents_uploaded_by', 'erp_documents', ['uploaded_by'], unique=False)


def downgrade():
    op.drop_index('ix_erp_documents_uploaded_by', table_name='erp_documents')
    op.drop_index('ix_erp_documents_workspace_id', table_name='erp_documents')
    op.drop_table('erp_documents')
