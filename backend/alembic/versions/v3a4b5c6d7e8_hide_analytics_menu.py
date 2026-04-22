"""Hide the per-module "Аналитика" menu entries

Every module (egg, incubation, factory, feed, slaughter) surfaced a
dedicated menu tab with read-only monthly-rollup tables
(`monthly-analytics`, `factory-monthly-analytics`,
`slaughter-monthly-analytics`). The rows are populated by Taskiq jobs
and cannot be edited by operators, so the tab only ever showed a
frozen grid of numbers that duplicated the real dashboards.

This migration flips `is_active = false` on every
`workspace_resources` row whose `key` ends with `-analytics`. The
tables, jobs and APIs stay intact — dashboards and reports still read
from them — but the menu no longer surfaces a standalone tab.

Revision ID: v3a4b5c6d7e8
Revises: u2f3a4b5c6d7
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op


revision = "v3a4b5c6d7e8"
down_revision = "u2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE workspace_resources
        SET is_active = false
        WHERE key LIKE '%-analytics'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE workspace_resources
        SET is_active = true
        WHERE key LIKE '%-analytics'
        """
    )
