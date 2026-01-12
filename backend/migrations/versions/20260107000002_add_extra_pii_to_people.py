"""add extra pii to people

Revision ID: 20260107000002
Revises: 20260107000001
Create Date: 2026-01-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260107000002'
down_revision = '20260107000001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('people', sa.Column('date_of_birth', sa.DateTime(), nullable=True))
    op.add_column('people', sa.Column('id_number', sa.String(), nullable=True))


def downgrade():
    op.drop_column('people', 'id_number')
    op.drop_column('people', 'date_of_birth')
