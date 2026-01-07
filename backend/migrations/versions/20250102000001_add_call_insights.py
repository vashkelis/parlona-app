"""Empty migration placeholder for call insights.

Revision ID: 20250102000001
Revises: 20250102000000
Create Date: 2025-01-02 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250102000001'
down_revision = '20250102000000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This migration is intentionally empty since all changes were already applied
    # in the previous migration. This is just to sync the revision number.
    pass


def downgrade() -> None:
    # This migration is intentionally empty since all changes were already applied
    # in the previous migration. This is just to sync the revision number.
    pass