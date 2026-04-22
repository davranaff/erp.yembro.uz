"""Drop `production_id` and `source_client_id` from incubation_batches

Operators no longer specify the upstream egg source when logging an
incubation batch — the form just records how many eggs were set,
without forcing a link back to the mother-flock's egg production row
or to an external supplier. Dropping the two nullable columns and
their FKs keeps the schema honest about that.

Revision ID: a8f9b0c1d2e3
Revises: z7e8f9a0b1c2
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "a8f9b0c1d2e3"
down_revision = "z7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE incubation_batches DROP COLUMN IF EXISTS production_id")
    op.execute("ALTER TABLE incubation_batches DROP COLUMN IF EXISTS source_client_id")


def downgrade() -> None:
    # Intentionally a no-op — the source linkage is gone from the code
    # path. Restore from a pre-drop backup if it ever needs to come back.
    pass
