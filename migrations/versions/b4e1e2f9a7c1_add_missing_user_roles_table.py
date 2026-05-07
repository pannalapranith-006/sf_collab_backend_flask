"""add missing user_roles table

Revision ID: b4e1e2f9a7c1
Revises: fa9d7c3b2e11
Create Date: 2026-04-18 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4e1e2f9a7c1'
down_revision = 'fa9d7c3b2e11'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    def column_exists(table_name, column_name):
        if table_name not in tables:
            return False
        return column_name in {column['name'] for column in inspector.get_columns(table_name)}

    if 'users' in tables and 'user_roles' not in tables:
        op.create_table(
            'user_roles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('role', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'role', name='unique_user_role')
        )

    if 'users' in tables and 'user_wallets' not in tables:
        op.create_table(
            'user_wallets',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('last_earning_reset', sa.DateTime(), nullable=True),
            sa.Column('sf_coins', sa.Integer(), nullable=True),
            sa.Column('premium_gems', sa.Integer(), nullable=True),
            sa.Column('event_tokens', sa.Integer(), nullable=True),
            sa.Column('credits', sa.Integer(), nullable=True),
            sa.Column('total_coins_earned', sa.Integer(), nullable=True),
            sa.Column('total_coins_spent', sa.Integer(), nullable=True),
            sa.Column('daily_earnings', sa.Integer(), nullable=True),
            sa.Column('daily_earning_limit', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', name='uq_user_wallets_user_id')
        )

    if 'users' in tables:
        if not column_exists('users', 'last_seen'):
            op.add_column('users', sa.Column('last_seen', sa.DateTime(), nullable=True))
        if not column_exists('users', 'builder_plan_id'):
            op.add_column('users', sa.Column('builder_plan_id', sa.String(length=255), nullable=True))
        if not column_exists('users', 'founder_plan_id'):
            op.add_column('users', sa.Column('founder_plan_id', sa.String(length=255), nullable=True))
        if not column_exists('users', 'stripe_connect_account_id'):
            op.add_column('users', sa.Column('stripe_connect_account_id', sa.String(length=255), nullable=True))
        if not column_exists('users', 'reputation_score'):
            op.add_column('users', sa.Column('reputation_score', sa.Float(), nullable=True))
        if not column_exists('users', 'milestones_completed'):
            op.add_column('users', sa.Column('milestones_completed', sa.Integer(), nullable=True))
        if not column_exists('users', 'milestones_on_time'):
            op.add_column('users', sa.Column('milestones_on_time', sa.Integer(), nullable=True))
        if not column_exists('users', 'tasks_completed'):
            op.add_column('users', sa.Column('tasks_completed', sa.Integer(), nullable=True))
        if not column_exists('users', 'tasks_on_time'):
            op.add_column('users', sa.Column('tasks_on_time', sa.Integer(), nullable=True))
        if not column_exists('users', 'collaborations_count'):
            op.add_column('users', sa.Column('collaborations_count', sa.Integer(), nullable=True))
        if not column_exists('users', 'storage_used_mb'):
            op.add_column('users', sa.Column('storage_used_mb', sa.Float(), nullable=False, server_default='0'))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'user_wallets' in tables:
        op.drop_table('user_wallets')
    if 'user_roles' in tables:
        op.drop_table('user_roles')