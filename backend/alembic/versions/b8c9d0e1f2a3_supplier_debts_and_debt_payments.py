"""supplier debts, debt payments and workspace resources

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
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


SUPPLIER_DEBT_MODULES = (
    ("core", "32000000-0000-0000-0000-000000000920", 46, False),
    ("egg", "32000000-0000-0000-0000-000000000921", 62, True),
    ("incubation", "32000000-0000-0000-0000-000000000922", 62, True),
    ("factory", "32000000-0000-0000-0000-000000000923", 87, True),
    ("feed", "32000000-0000-0000-0000-000000000924", 87, True),
    ("medicine", "32000000-0000-0000-0000-000000000925", 77, True),
    ("slaughter", "32000000-0000-0000-0000-000000000926", 72, True),
)

DEBT_PAYMENT_MODULES = (
    ("finance", "32000000-0000-0000-0000-000000000930", 20, True),
)


def _supplier_debt_resources() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for module_key, resource_id, sort_order, visible in SUPPLIER_DEBT_MODULES:
        rows.append(
            {
                "id": resource_id,
                "module_key": module_key,
                "key": "supplier-debts",
                "name": "Долги поставщикам",
                "path": "supplier-debts",
                "description": "Кредиторская задолженность перед поставщиками",
                "permission_prefix": "supplier_debt",
                "api_module_key": None if module_key in {"core", "finance"} else "finance",
                "sort_order": sort_order,
                "is_head_visible": visible,
                "is_active": True,
            }
        )
    return tuple(rows)


def _debt_payment_resources() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for module_key, resource_id, sort_order, visible in DEBT_PAYMENT_MODULES:
        rows.append(
            {
                "id": resource_id,
                "module_key": module_key,
                "key": "debt-payments",
                "name": "Погашения долгов",
                "path": "debt-payments",
                "description": "История погашений по долгам клиентов и поставщиков",
                "permission_prefix": "debt_payment",
                "api_module_key": None,
                "sort_order": sort_order,
                "is_head_visible": visible,
                "is_active": True,
            }
        )
    return tuple(rows)


def _insert_workspace_resources(bind, resources) -> None:
    for resource in resources:
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


def _delete_workspace_resources(bind, resources) -> None:
    for resource in resources:
        bind.execute(
            workspace_resources_table.delete().where(
                workspace_resources_table.c.module_key == resource["module_key"],
                workspace_resources_table.c.key == resource["key"],
            )
        )


def upgrade() -> None:
    op.create_table(
        "supplier_debts",
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
        sa.CheckConstraint("quantity > 0", name="ck_supplier_debt_quantity_positive"),
        sa.CheckConstraint("amount_total >= 0", name="ck_supplier_debt_amount_total_non_negative"),
        sa.CheckConstraint("amount_paid >= 0", name="ck_supplier_debt_amount_paid_non_negative"),
        sa.CheckConstraint("amount_paid <= amount_total", name="ck_supplier_debt_amount_paid_not_exceed_total"),
        sa.CheckConstraint("(due_on IS NULL) OR (due_on >= issued_on)", name="ck_supplier_debt_due_not_before_issued"),
        sa.CheckConstraint(
            "status IN ('open', 'partially_paid', 'closed', 'cancelled')",
            name="ck_supplier_debt_status",
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
            name="uq_supplier_debt_scope_item_date",
        ),
    )
    op.create_index(op.f("ix_supplier_debts_organization_id"), "supplier_debts", ["organization_id"], unique=False)
    op.create_index(op.f("ix_supplier_debts_department_id"), "supplier_debts", ["department_id"], unique=False)
    op.create_index(op.f("ix_supplier_debts_client_id"), "supplier_debts", ["client_id"], unique=False)
    op.create_index(op.f("ix_supplier_debts_item_type"), "supplier_debts", ["item_type"], unique=False)
    op.create_index(op.f("ix_supplier_debts_item_key"), "supplier_debts", ["item_key"], unique=False)
    op.create_index(op.f("ix_supplier_debts_issued_on"), "supplier_debts", ["issued_on"], unique=False)
    op.create_index(op.f("ix_supplier_debts_due_on"), "supplier_debts", ["due_on"], unique=False)
    op.create_index(op.f("ix_supplier_debts_status"), "supplier_debts", ["status"], unique=False)

    op.create_table(
        "debt_payments",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("client_debt_id", sa.UUID(), nullable=True),
        sa.Column("supplier_debt_id", sa.UUID(), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("method", sa.String(length=24), nullable=False, server_default="cash"),
        sa.Column("reference_no", sa.String(length=120), nullable=True),
        sa.Column("cash_account_id", sa.UUID(), nullable=True),
        sa.Column("cash_transaction_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_debt_payment_amount_positive"),
        sa.CheckConstraint(
            "direction IN ('incoming', 'outgoing')",
            name="ck_debt_payment_direction_allowed",
        ),
        sa.CheckConstraint(
            "method IN ('cash', 'bank', 'card', 'transfer', 'offset', 'other')",
            name="ck_debt_payment_method_allowed",
        ),
        sa.CheckConstraint(
            "(client_debt_id IS NOT NULL AND supplier_debt_id IS NULL) OR "
            "(client_debt_id IS NULL AND supplier_debt_id IS NOT NULL)",
            name="ck_debt_payment_exactly_one_parent",
        ),
        sa.CheckConstraint(
            "(direction = 'incoming' AND client_debt_id IS NOT NULL) OR "
            "(direction = 'outgoing' AND supplier_debt_id IS NOT NULL)",
            name="ck_debt_payment_direction_matches_parent",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_debt_id"], ["client_debts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_debt_id"], ["supplier_debts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cash_transaction_id"], ["cash_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["employees.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_debt_payments_organization_id"), "debt_payments", ["organization_id"], unique=False)
    op.create_index(op.f("ix_debt_payments_department_id"), "debt_payments", ["department_id"], unique=False)
    op.create_index(op.f("ix_debt_payments_client_debt_id"), "debt_payments", ["client_debt_id"], unique=False)
    op.create_index(op.f("ix_debt_payments_supplier_debt_id"), "debt_payments", ["supplier_debt_id"], unique=False)
    op.create_index(op.f("ix_debt_payments_direction"), "debt_payments", ["direction"], unique=False)
    op.create_index(op.f("ix_debt_payments_paid_on"), "debt_payments", ["paid_on"], unique=False)
    op.create_index(op.f("ix_debt_payments_method"), "debt_payments", ["method"], unique=False)
    op.create_index(op.f("ix_debt_payments_reference_no"), "debt_payments", ["reference_no"], unique=False)
    op.create_index(op.f("ix_debt_payments_cash_account_id"), "debt_payments", ["cash_account_id"], unique=False)
    op.create_index(op.f("ix_debt_payments_cash_transaction_id"), "debt_payments", ["cash_transaction_id"], unique=False)
    op.create_index(op.f("ix_debt_payments_created_by"), "debt_payments", ["created_by"], unique=False)

    bind = op.get_bind()
    _insert_workspace_resources(bind, _supplier_debt_resources())
    _insert_workspace_resources(bind, _debt_payment_resources())


def downgrade() -> None:
    bind = op.get_bind()
    _delete_workspace_resources(bind, _debt_payment_resources())
    _delete_workspace_resources(bind, _supplier_debt_resources())

    op.drop_index(op.f("ix_debt_payments_created_by"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_cash_transaction_id"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_cash_account_id"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_reference_no"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_method"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_paid_on"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_direction"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_supplier_debt_id"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_client_debt_id"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_department_id"), table_name="debt_payments")
    op.drop_index(op.f("ix_debt_payments_organization_id"), table_name="debt_payments")
    op.drop_table("debt_payments")

    op.drop_index(op.f("ix_supplier_debts_status"), table_name="supplier_debts")
    op.drop_index(op.f("ix_supplier_debts_due_on"), table_name="supplier_debts")
    op.drop_index(op.f("ix_supplier_debts_issued_on"), table_name="supplier_debts")
    op.drop_index(op.f("ix_supplier_debts_item_key"), table_name="supplier_debts")
    op.drop_index(op.f("ix_supplier_debts_item_type"), table_name="supplier_debts")
    op.drop_index(op.f("ix_supplier_debts_client_id"), table_name="supplier_debts")
    op.drop_index(op.f("ix_supplier_debts_department_id"), table_name="supplier_debts")
    op.drop_index(op.f("ix_supplier_debts_organization_id"), table_name="supplier_debts")
    op.drop_table("supplier_debts")
