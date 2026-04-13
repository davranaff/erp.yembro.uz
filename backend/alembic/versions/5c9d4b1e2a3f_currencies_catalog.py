"""currencies catalog

Revision ID: 5c9d4b1e2a3f
Revises: 4e6f8a9b1c2d
Create Date: 2026-03-25 16:30:00.000000
"""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "5c9d4b1e2a3f"
down_revision = "4e6f8a9b1c2d"
branch_labels = None
depends_on = None


organizations_table = sa.table(
    "organizations",
    sa.column("id", sa.UUID()),
)

currencies_table = sa.table(
    "currencies",
    sa.column("id", sa.UUID()),
    sa.column("organization_id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("symbol", sa.String()),
    sa.column("description", sa.String()),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_default", sa.Boolean()),
    sa.column("is_active", sa.Boolean()),
)

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.UUID()),
    sa.column("organization_id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("resource", sa.String()),
    sa.column("action", sa.String()),
    sa.column("description", sa.String()),
    sa.column("is_active", sa.Boolean()),
)

roles_table = sa.table(
    "roles",
    sa.column("id", sa.UUID()),
    sa.column("organization_id", sa.UUID()),
    sa.column("slug", sa.String()),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", sa.UUID()),
    sa.column("permission_id", sa.UUID()),
)

DEFAULT_PERMISSION_DESCRIPTIONS = {
    "read": "View currencies",
    "create": "Create currencies",
    "write": "Update currencies",
    "delete": "Delete currencies",
}

DEFAULT_SYMBOLS = {
    "UZS": "so'm",
    "USD": "$",
    "EUR": "EUR",
    "RUB": "RUB",
}

CURRENCY_SOURCE_TABLES = (
    "cash_accounts",
    "cash_transactions",
    "expenses",
    "egg_monthly_analytics",
    "egg_shipments",
    "chick_arrivals",
    "chick_shipments",
    "feed_arrivals",
    "feed_raw_arrivals",
    "feed_product_shipments",
    "medicine_arrivals",
    "medicine_batches",
    "slaughter_arrivals",
    "slaughter_semi_product_shipments",
)


def _build_currency_seed_query() -> sa.TextClause:
    union_sql = " UNION ALL ".join(
        f"""
        SELECT organization_id, UPPER(BTRIM(currency)) AS code
        FROM {table_name}
        WHERE currency IS NOT NULL
          AND BTRIM(currency) <> ''
        """
        for table_name in CURRENCY_SOURCE_TABLES
    )
    return sa.text(f"SELECT DISTINCT organization_id, code FROM ({union_sql}) AS seeded")


def upgrade() -> None:
    op.create_table(
        "currencies",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="100", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_currency_org_code"),
        sa.UniqueConstraint("organization_id", "name", name="uq_currency_org_name"),
    )
    op.create_index(op.f("ix_currencies_id"), "currencies", ["id"], unique=False)
    op.create_index(op.f("ix_currencies_code"), "currencies", ["code"], unique=False)
    op.create_index(op.f("ix_currencies_name"), "currencies", ["name"], unique=False)
    op.create_index(op.f("ix_currencies_organization_id"), "currencies", ["organization_id"], unique=False)
    op.create_index(op.f("ix_currencies_sort_order"), "currencies", ["sort_order"], unique=False)

    bind = op.get_bind()
    organizations = list(bind.execute(sa.select(organizations_table.c.id)).mappings())
    seeded_rows = list(bind.execute(_build_currency_seed_query()).mappings())

    currency_codes_by_org: dict[object, set[str]] = {}
    for row in seeded_rows:
        organization_id = row["organization_id"]
        code = str(row["code"]).strip().upper()
        if not code:
            continue
        currency_codes_by_org.setdefault(organization_id, set()).add(code)

    for organization in organizations:
        organization_id = organization["id"]
        codes = currency_codes_by_org.setdefault(organization_id, set())
        if not codes:
            codes.add("UZS")

        ordered_codes = sorted(codes)
        default_code = "UZS" if "UZS" in codes else ordered_codes[0]
        for index, code in enumerate(ordered_codes, start=1):
            bind.execute(
                currencies_table.insert().values(
                    id=uuid4(),
                    organization_id=organization_id,
                    code=code,
                    name=code,
                    symbol=DEFAULT_SYMBOLS.get(code),
                    description=None,
                    sort_order=index * 10,
                    is_default=(code == default_code),
                    is_active=True,
                )
            )

    permission_ids_by_org_and_code: dict[tuple[object, str], object] = {}
    for organization in organizations:
        organization_id = organization["id"]
        for action, description in DEFAULT_PERMISSION_DESCRIPTIONS.items():
            code = f"currency.{action}"
            existing_permission_id = bind.execute(
                sa.select(permissions_table.c.id).where(
                    permissions_table.c.organization_id == organization_id,
                    permissions_table.c.code == code,
                )
            ).scalar_one_or_none()

            if existing_permission_id is None:
                existing_permission_id = uuid4()
                bind.execute(
                    permissions_table.insert().values(
                        id=existing_permission_id,
                        organization_id=organization_id,
                        code=code,
                        resource="currency",
                        action=action,
                        description=description,
                        is_active=True,
                    )
                )
            permission_ids_by_org_and_code[(organization_id, code)] = existing_permission_id

    admin_roles = list(
        bind.execute(
            sa.select(roles_table.c.id, roles_table.c.organization_id).where(
                roles_table.c.slug.in_(("admin", "manager"))
            )
        ).mappings()
    )

    for role in admin_roles:
        organization_id = role["organization_id"]
        for action in DEFAULT_PERMISSION_DESCRIPTIONS:
            permission_id = permission_ids_by_org_and_code.get((organization_id, f"currency.{action}"))
            if permission_id is None:
                continue

            existing_assignment = bind.execute(
                sa.select(role_permissions_table.c.role_id).where(
                    role_permissions_table.c.role_id == role["id"],
                    role_permissions_table.c.permission_id == permission_id,
                )
            ).scalar_one_or_none()
            if existing_assignment is not None:
                continue

            bind.execute(
                role_permissions_table.insert().values(
                    role_id=role["id"],
                    permission_id=permission_id,
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    permission_rows = list(
        bind.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.resource == "currency"
            )
        ).mappings()
    )
    permission_ids = [row["id"] for row in permission_rows]
    if permission_ids:
        bind.execute(
            role_permissions_table.delete().where(role_permissions_table.c.permission_id.in_(permission_ids))
        )
        bind.execute(permissions_table.delete().where(permissions_table.c.id.in_(permission_ids)))

    op.drop_index(op.f("ix_currencies_sort_order"), table_name="currencies")
    op.drop_index(op.f("ix_currencies_organization_id"), table_name="currencies")
    op.drop_index(op.f("ix_currencies_name"), table_name="currencies")
    op.drop_index(op.f("ix_currencies_code"), table_name="currencies")
    op.drop_index(op.f("ix_currencies_id"), table_name="currencies")
    op.drop_table("currencies")
