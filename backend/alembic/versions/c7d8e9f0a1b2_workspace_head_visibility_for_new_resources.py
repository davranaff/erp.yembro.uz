"""workspace head visibility for new resources

Revision ID: c7d8e9f0a1b2
Revises: b3e6a9d2c4f1
Create Date: 2026-03-30 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c7d8e9f0a1b2"
down_revision = "b3e6a9d2c4f1"
branch_labels = None
depends_on = None


workspace_resources_table = sa.table(
    "workspace_resources",
    sa.column("module_key", sa.String()),
    sa.column("key", sa.String()),
    sa.column("is_head_visible", sa.Boolean()),
)


RESOURCE_KEYS: tuple[tuple[str, str], ...] = (
    ("egg", "stock-movements"),
    ("incubation", "monthly-analytics"),
    ("incubation", "factory-monthly-analytics"),
    ("incubation", "stock-movements"),
    ("factory", "stock-movements"),
    ("feed", "types"),
    ("feed", "stock-movements"),
    ("medicine", "stock-movements"),
    ("slaughter", "stock-movements"),
)


def _set_head_visibility(value: bool) -> None:
    bind = op.get_bind()
    for module_key, resource_key in RESOURCE_KEYS:
        bind.execute(
            workspace_resources_table.update()
            .where(
                workspace_resources_table.c.module_key == module_key,
                workspace_resources_table.c.key == resource_key,
            )
            .values(is_head_visible=value)
        )


def upgrade() -> None:
    _set_head_visibility(True)


def downgrade() -> None:
    _set_head_visibility(False)
