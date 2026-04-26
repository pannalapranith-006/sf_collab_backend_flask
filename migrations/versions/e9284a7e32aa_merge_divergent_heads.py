"""Merge divergent heads

Revision ID: e9284a7e32aa
Revises: 3ef7a4fe1172, c18d8dd600f4
Create Date: 2026-03-17 17:57:56.301541

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9284a7e32aa'
down_revision = ('3ef7a4fe1172', 'c18d8dd600f4')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
