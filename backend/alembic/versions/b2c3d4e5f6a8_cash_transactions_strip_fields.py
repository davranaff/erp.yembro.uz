"""Strip counterparty + status fields from cash_transactions

Operators stopped filling counterparty and posting-status on cash
transactions through the form — drop the four columns from the table:

* ``counterparty_client_id`` (legacy FK to clients)
* ``counterparty_type``, ``counterparty_id`` (polymorphic pair that
  only ever mirrored ``counterparty_client_id``)
* ``status`` (``posted``/``void`` lifecycle that nothing on the backend
  actually branches on)

``source_type`` / ``source_id`` stay — they're system-internal links
from debt-payment/advance auto-sync and are still used by the
advance-balance aggregate.

Revision ID: b2c3d4e5f6a8
Revises: e4f5a6b7c8d9
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "b2c3d4e5f6a8"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE cash_transactions DROP COLUMN IF EXISTS counterparty_client_id")
    op.execute("ALTER TABLE cash_transactions DROP COLUMN IF EXISTS counterparty_type")
    op.execute("ALTER TABLE cash_transactions DROP COLUMN IF EXISTS counterparty_id")
    op.execute("ALTER TABLE cash_transactions DROP COLUMN IF EXISTS status")


def downgrade() -> None:
    pass
