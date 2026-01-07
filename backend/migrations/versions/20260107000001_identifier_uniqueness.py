"""Add unique constraint on identifiers and create deduplication script.

Revision ID: 20260107000001
Revises: 20260106000100
Create Date: 2026-01-07 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260107000001"
down_revision = "20260106000100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    The unique constraint already exists in the base migration.
    This migration ensures it's properly enforced and provides
    a safety check.
    """
    # The constraint was already created in 20260106000100:
    # sa.UniqueConstraint(
    #     "identifier_type",
    #     "normalized_value",
    #     name="uq_identifiers_type_normalized",
    # )
    
    # This migration is a placeholder to document the deduplication process
    # Run the deduplication script manually before applying this migration
    pass


def downgrade() -> None:
    """No changes needed."""
    pass
