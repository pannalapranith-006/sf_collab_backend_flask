"""merge erp and drive heads

Revision ID: 2a8cc8b1870a
Revises: 672e6bf46139, f1bba4d86c70
Create Date: 2026-04-25 09:52:38.088336

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a8cc8b1870a'
down_revision = ('672e6bf46139', 'f1bba4d86c70')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
