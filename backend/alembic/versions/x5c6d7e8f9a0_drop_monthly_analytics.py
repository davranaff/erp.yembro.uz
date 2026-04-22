"""Drop the 5 monthly-analytics rollup tables

The dashboard now computes monthly trends live from source operational
tables (slaughter_processings, slaughter_semi_product_shipments, etc.),
the Taskiq job that populated these rollups was removed, and every
menu entry + CRUD route + model/schema/service that referenced them
is gone from the codebase. Dropping the tables closes the loop.

Tables dropped (CASCADE to cut dependent indexes/constraints):
  egg_monthly_analytics
  feed_monthly_analytics
  incubation_monthly_analytics
  factory_monthly_analytics
  slaughter_monthly_analytics

Also cleans up any lingering workspace_resources rows whose key ends
with ``-analytics`` (they were deactivated by a prior migration; now
we just remove them outright).

Revision ID: x5c6d7e8f9a0
Revises: w4b5c6d7e8f9
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op


revision = "x5c6d7e8f9a0"
down_revision = "w4b5c6d7e8f9"
branch_labels = None
depends_on = None


TABLES = (
    "egg_monthly_analytics",
    "feed_monthly_analytics",
    "incubation_monthly_analytics",
    "factory_monthly_analytics",
    "slaughter_monthly_analytics",
)


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM workspace_resources
        WHERE key LIKE '%-analytics'
        """
    )

    for table in TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')


def downgrade() -> None:
    # Intentionally a no-op: the data model and fixture pipeline are
    # gone, so there's nothing meaningful to recreate. Restore from a
    # pre-drop backup if you really need the rollup tables back.
    pass
