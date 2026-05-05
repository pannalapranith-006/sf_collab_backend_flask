"""merge current heads

Revision ID: fa9d7c3b2e11
Revises: 3ef7a4fe1172, c18d8dd600f4
Create Date: 2026-04-03 15:12:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fa9d7c3b2e11'
down_revision = ('3ef7a4fe1172', 'c18d8dd600f4')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
