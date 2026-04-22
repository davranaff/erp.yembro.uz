"""Currency exchange rates history (CBU integration)

Adds a ``currency_exchange_rates`` table that captures the daily
exchange-rate-to-base snapshot for every non-base currency in every
organization. The rate for a cash transaction / debt payment / arrival
/ shipment etc. is now looked up against this table instead of being
blindly trusted from the user payload, so that:

* money moved in USD on 2026-04-21 is always priced with the 2026-04-21
  CBU rate, even if someone edits the transaction later;
* users can browse a full history of what the rate was on any given
  day.

Rows come from two sources:

* ``source = 'cbu'`` — inserted by the daily Taskiq sync job that hits
  https://cbu.uz/ru/arkhiv-kursov-valyut/json/ (or the per-currency
  endpoint), one row per (organization, currency, date).
* ``source = 'manual'`` — inserted by an admin via the API.

The ``UniqueConstraint`` guarantees a single rate per
(organization, currency, date) so the sync job can safely upsert.

Downgrade drops the table entirely.

Revision ID: c0d1e2f3a4b5
Revises: b9a0c1d2e3f4
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c0d1e2f3a4b5"
down_revision = "b9a0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "currency_exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "currency_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("currencies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="cbu"),
        sa.Column("source_ref", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("rate > 0", name="ck_currency_rate_positive"),
        sa.UniqueConstraint(
            "organization_id",
            "currency_id",
            "rate_date",
            name="uq_currency_rate_org_currency_date",
        ),
    )
    op.create_index(
        "ix_currency_exchange_rates_organization_id",
        "currency_exchange_rates",
        ["organization_id"],
    )
    op.create_index(
        "ix_currency_exchange_rates_currency_id",
        "currency_exchange_rates",
        ["currency_id"],
    )
    op.create_index(
        "ix_currency_exchange_rates_rate_date",
        "currency_exchange_rates",
        ["rate_date"],
    )
    op.create_index(
        "ix_currency_exchange_rates_source",
        "currency_exchange_rates",
        ["source"],
    )
    op.create_index(
        "ix_currency_rate_org_currency_date",
        "currency_exchange_rates",
        ["organization_id", "currency_id", "rate_date"],
    )

    # Backfill a rate for the base currency on today's date so that
    # resolve_exchange_rate() always has something to return for it
    # even before the CBU sync job runs.
    op.execute(
        """
        INSERT INTO currency_exchange_rates (
            id, organization_id, currency_id, rate_date, rate, source,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            c.organization_id,
            c.id,
            CURRENT_DATE,
            1,
            'seed',
            NOW(),
            NOW()
        FROM currencies c
        WHERE c.is_default = true
        ON CONFLICT (organization_id, currency_id, rate_date) DO NOTHING
        """
    )

    # --- Permissions for the new resource --------------------------------
    op.execute(
        """
        INSERT INTO permissions (id, organization_id, code, resource, action, description, is_active)
        SELECT
            gen_random_uuid(),
            o.id,
            'currency_exchange_rate.' || act.code,
            'currency_exchange_rate',
            act.code,
            act.description,
            true
        FROM organizations o
        CROSS JOIN (
            VALUES
                ('read',   'Просмотр курсов валют'),
                ('create', 'Создание курса валюты'),
                ('write',  'Редактирование курса валюты'),
                ('delete', 'Удаление курса валюты')
        ) AS act(code, description)
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions p
            WHERE p.organization_id = o.id
              AND p.code = 'currency_exchange_rate.' || act.code
        )
        """
    )

    # Assign the new permissions to admin and manager roles.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.organization_id = r.organization_id
        WHERE r.slug IN ('admin', 'manager')
          AND p.code LIKE 'currency_exchange_rate.%'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE resource = 'currency_exchange_rate'")
    op.drop_index(
        "ix_currency_rate_org_currency_date", table_name="currency_exchange_rates"
    )
    op.drop_index(
        "ix_currency_exchange_rates_source", table_name="currency_exchange_rates"
    )
    op.drop_index(
        "ix_currency_exchange_rates_rate_date", table_name="currency_exchange_rates"
    )
    op.drop_index(
        "ix_currency_exchange_rates_currency_id", table_name="currency_exchange_rates"
    )
    op.drop_index(
        "ix_currency_exchange_rates_organization_id",
        table_name="currency_exchange_rates",
    )
    op.drop_table("currency_exchange_rates")
