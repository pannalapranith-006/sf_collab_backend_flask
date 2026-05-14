"""add workspace foundation tables

Revision ID: 91a_workspace_foundation
Revises: fa9d7c3b2e11
Create Date: 2026-04-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91a_workspace_foundation'
down_revision = 'fa9d7c3b2e11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('owner_user_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_workspaces_slug', 'workspaces', ['slug'], unique=False)
    op.create_index('ix_workspaces_owner_user_id', 'workspaces', ['owner_user_id'], unique=False)

    op.create_table(
        'workspace_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Enum('admin', 'member', name='workspace_role_enum'), nullable=False, server_default='member'),
        sa.Column('status', sa.Enum('active', 'invited', 'suspended', name='workspace_status_enum'), nullable=False, server_default='active'),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_members_workspace_user'),
    )
    op.create_index('ix_workspace_members_workspace_id', 'workspace_members', ['workspace_id'], unique=False)
    op.create_index('ix_workspace_members_user_id', 'workspace_members', ['user_id'], unique=False)


def downgrade():
    op.drop_index('ix_workspace_members_user_id', table_name='workspace_members')
    op.drop_index('ix_workspace_members_workspace_id', table_name='workspace_members')
    op.drop_table('workspace_members')

    op.drop_index('ix_workspaces_owner_user_id', table_name='workspaces')
    op.drop_index('ix_workspaces_slug', table_name='workspaces')
    op.drop_table('workspaces')
