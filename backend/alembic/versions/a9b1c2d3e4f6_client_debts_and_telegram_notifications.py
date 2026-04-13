"""client debts and telegram notifications

Revision ID: a9b1c2d3e4f6
Revises: f4a5b6c7d8e9
Create Date: 2026-04-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a9b1c2d3e4f6"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


workspace_resources_table = sa.table(
    "workspace_resources",
    sa.column("id", sa.UUID()),
    sa.column("module_key", sa.String()),
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("path", sa.String()),
    sa.column("description", sa.String()),
    sa.column("permission_prefix", sa.String()),
    sa.column("api_module_key", sa.String()),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_head_visible", sa.Boolean()),
    sa.column("is_active", sa.Boolean()),
)


WORKSPACE_CLIENT_DEBT_RESOURCES = (
    {
        "id": "32000000-0000-0000-0000-000000000901",
        "module_key": "core",
        "key": "client-debts",
        "name": "Долги клиентов",
        "path": "client-debts",
        "description": "Управление долгами клиентов",
        "permission_prefix": "client_debt",
        "api_module_key": None,
        "sort_order": 45,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000902",
        "module_key": "egg",
        "key": "client-debts",
        "name": "Долги клиентов",
        "path": "client-debts",
        "description": "Долги клиентов по модулю",
        "permission_prefix": "client_debt",
        "api_module_key": "core",
        "sort_order": 61,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000903",
        "module_key": "incubation",
        "key": "client-debts",
        "name": "Долги клиентов",
        "path": "client-debts",
        "description": "Долги клиентов по модулю",
        "permission_prefix": "client_debt",
        "api_module_key": "core",
        "sort_order": 61,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000904",
        "module_key": "factory",
        "key": "client-debts",
        "name": "Долги клиентов",
        "path": "client-debts",
        "description": "Долги клиентов по модулю",
        "permission_prefix": "client_debt",
        "api_module_key": "core",
        "sort_order": 86,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000905",
        "module_key": "feed",
        "key": "client-debts",
        "name": "Долги клиентов",
        "path": "client-debts",
        "description": "Долги клиентов по модулю",
        "permission_prefix": "client_debt",
        "api_module_key": "core",
        "sort_order": 86,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000906",
        "module_key": "medicine",
        "key": "client-debts",
        "name": "Долги клиентов",
        "path": "client-debts",
        "description": "Долги клиентов по модулю",
        "permission_prefix": "client_debt",
        "api_module_key": "core",
        "sort_order": 76,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000907",
        "module_key": "slaughter",
        "key": "client-debts",
        "name": "Долги клиентов",
        "path": "client-debts",
        "description": "Долги клиентов по модулю",
        "permission_prefix": "client_debt",
        "api_module_key": "core",
        "sort_order": 71,
        "is_head_visible": True,
        "is_active": True,
    },
)


def upgrade() -> None:
    op.add_column("clients", sa.Column("telegram_chat_id", sa.String(length=80), nullable=True))
    op.create_index(op.f("ix_clients_telegram_chat_id"), "clients", ["telegram_chat_id"], unique=False)

    op.create_table(
        "client_debts",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("item_type", sa.String(length=24), nullable=False),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=16, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="pcs"),
        sa.Column("amount_total", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(precision=16, scale=2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_client_debt_quantity_positive"),
        sa.CheckConstraint("amount_total >= 0", name="ck_client_debt_amount_total_non_negative"),
        sa.CheckConstraint("amount_paid >= 0", name="ck_client_debt_amount_paid_non_negative"),
        sa.CheckConstraint("amount_paid <= amount_total", name="ck_client_debt_amount_paid_not_exceed_total"),
        sa.CheckConstraint("(due_on IS NULL) OR (due_on >= issued_on)", name="ck_client_debt_due_not_before_issued"),
        sa.CheckConstraint(
            "status IN ('open', 'partially_paid', 'closed', 'cancelled')",
            name="ck_client_debt_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "department_id",
            "client_id",
            "item_key",
            "issued_on",
            name="uq_client_debt_scope_item_date",
        ),
    )
    op.create_index(op.f("ix_client_debts_organization_id"), "client_debts", ["organization_id"], unique=False)
    op.create_index(op.f("ix_client_debts_department_id"), "client_debts", ["department_id"], unique=False)
    op.create_index(op.f("ix_client_debts_client_id"), "client_debts", ["client_id"], unique=False)
    op.create_index(op.f("ix_client_debts_item_type"), "client_debts", ["item_type"], unique=False)
    op.create_index(op.f("ix_client_debts_item_key"), "client_debts", ["item_key"], unique=False)
    op.create_index(op.f("ix_client_debts_issued_on"), "client_debts", ["issued_on"], unique=False)
    op.create_index(op.f("ix_client_debts_due_on"), "client_debts", ["due_on"], unique=False)
    op.create_index(op.f("ix_client_debts_status"), "client_debts", ["status"], unique=False)

    bind = op.get_bind()
    for resource in WORKSPACE_CLIENT_DEBT_RESOURCES:
        exists = bind.execute(
            sa.select(workspace_resources_table.c.id).where(
                workspace_resources_table.c.module_key == resource["module_key"],
                workspace_resources_table.c.key == resource["key"],
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue

        bind.execute(
            workspace_resources_table.insert().values(
                id=resource["id"],
                module_key=resource["module_key"],
                key=resource["key"],
                name=resource["name"],
                path=resource["path"],
                description=resource["description"],
                permission_prefix=resource["permission_prefix"],
                api_module_key=resource["api_module_key"],
                sort_order=resource["sort_order"],
                is_head_visible=resource["is_head_visible"],
                is_active=resource["is_active"],
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    for resource in WORKSPACE_CLIENT_DEBT_RESOURCES:
        bind.execute(
            workspace_resources_table.delete().where(
                workspace_resources_table.c.module_key == resource["module_key"],
                workspace_resources_table.c.key == resource["key"],
            )
        )

    op.drop_index(op.f("ix_client_debts_status"), table_name="client_debts")
    op.drop_index(op.f("ix_client_debts_due_on"), table_name="client_debts")
    op.drop_index(op.f("ix_client_debts_issued_on"), table_name="client_debts")
    op.drop_index(op.f("ix_client_debts_item_key"), table_name="client_debts")
    op.drop_index(op.f("ix_client_debts_item_type"), table_name="client_debts")
    op.drop_index(op.f("ix_client_debts_client_id"), table_name="client_debts")
    op.drop_index(op.f("ix_client_debts_department_id"), table_name="client_debts")
    op.drop_index(op.f("ix_client_debts_organization_id"), table_name="client_debts")
    op.drop_table("client_debts")

    op.drop_index(op.f("ix_clients_telegram_chat_id"), table_name="clients")
    op.drop_column("clients", "telegram_chat_id")
