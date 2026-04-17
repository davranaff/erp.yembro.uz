"""Slaughter hybrid arrival: factory shipment OR external supplier, inline on processing

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-04-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns to slaughter_processings (all nullable initially for back-fill)
    op.add_column(
        "slaughter_processings",
        sa.Column("source_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("factory_shipment_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("supplier_client_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrived_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("birds_received", sa.Integer(), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_total_weight_kg", sa.Numeric(16, 3), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_unit_price", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_currency", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_invoice_no", sa.String(length=120), nullable=True),
    )

    # 2. Backfill from slaughter_arrivals (all existing processings are external)
    op.execute(
        """
        UPDATE slaughter_processings sp
        SET
            source_type = 'external',
            supplier_client_id = sa.supplier_client_id,
            arrived_on = sa.arrived_on,
            birds_received = sa.birds_count,
            arrival_total_weight_kg = CASE
                WHEN sa.average_weight_kg IS NOT NULL AND sa.birds_count IS NOT NULL
                THEN ROUND(sa.average_weight_kg * sa.birds_count, 3)
                ELSE NULL
            END,
            arrival_unit_price = sa.unit_price,
            arrival_currency = sa.currency,
            arrival_invoice_no = sa.invoice_no
        FROM slaughter_arrivals sa
        WHERE sp.arrival_id = sa.id
        """
    )

    # Defensive: processings without a matching arrival — mark as external stub.
    # Supplier FK must be non-null for external; fall back to any client for the org.
    op.execute(
        """
        UPDATE slaughter_processings sp
        SET
            source_type = 'external',
            supplier_client_id = COALESCE(
                sp.supplier_client_id,
                (SELECT c.id FROM clients c WHERE c.organization_id = sp.organization_id ORDER BY c.created_at LIMIT 1)
            ),
            arrived_on = COALESCE(sp.arrived_on, sp.processed_on),
            birds_received = COALESCE(sp.birds_received, sp.birds_processed)
        WHERE sp.source_type IS NULL
        """
    )

    # 3. Drop the old unique constraint and FK/column on arrival_id
    op.drop_constraint(
        "uq_slaughter_processing_arrival_date",
        "slaughter_processings",
        type_="unique",
    )
    op.drop_index(
        "ix_slaughter_processings_arrival_id",
        table_name="slaughter_processings",
    )
    # FK name may differ across envs — drop by referenced table via reflection
    op.execute(
        """
        DO $$
        DECLARE fk_name text;
        BEGIN
            SELECT tc.constraint_name INTO fk_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_name = kcu.table_name
            WHERE tc.table_name = 'slaughter_processings'
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'arrival_id'
            LIMIT 1;
            IF fk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE slaughter_processings DROP CONSTRAINT %I', fk_name);
            END IF;
        END $$;
        """
    )
    op.drop_column("slaughter_processings", "arrival_id")

    # 4. Tighten new columns to NOT NULL
    op.alter_column("slaughter_processings", "source_type", nullable=False)
    op.alter_column("slaughter_processings", "arrived_on", nullable=False)
    op.alter_column("slaughter_processings", "birds_received", nullable=False)

    # 5. Indexes for new FKs + fields
    op.create_index(
        "ix_slaughter_processings_source_type",
        "slaughter_processings",
        ["source_type"],
    )
    op.create_index(
        "ix_slaughter_processings_factory_shipment_id",
        "slaughter_processings",
        ["factory_shipment_id"],
    )
    op.create_index(
        "ix_slaughter_processings_supplier_client_id",
        "slaughter_processings",
        ["supplier_client_id"],
    )
    op.create_index(
        "ix_slaughter_processings_arrived_on",
        "slaughter_processings",
        ["arrived_on"],
    )

    # 6. FKs on new columns
    op.create_foreign_key(
        "fk_slaughter_processings_factory_shipment_id",
        "slaughter_processings",
        "factory_shipments",
        ["factory_shipment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_slaughter_processings_supplier_client_id",
        "slaughter_processings",
        "clients",
        ["supplier_client_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 7. Check constraints
    op.create_check_constraint(
        "ck_slaughter_processing_source_type",
        "slaughter_processings",
        "source_type IN ('factory', 'external')",
    )
    op.create_check_constraint(
        "ck_slaughter_processing_source_exactly_one",
        "slaughter_processings",
        "(source_type = 'factory' AND factory_shipment_id IS NOT NULL AND supplier_client_id IS NULL) OR "
        "(source_type = 'external' AND supplier_client_id IS NOT NULL AND factory_shipment_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_slaughter_processing_birds_received_non_negative",
        "slaughter_processings",
        "birds_received >= 0",
    )
    op.create_check_constraint(
        "ck_slaughter_processing_processed_not_exceed_received",
        "slaughter_processings",
        "birds_processed <= birds_received",
    )
    op.create_check_constraint(
        "ck_slaughter_processing_arrival_total_weight_non_negative",
        "slaughter_processings",
        "arrival_total_weight_kg IS NULL OR arrival_total_weight_kg >= 0",
    )
    op.create_check_constraint(
        "ck_slaughter_processing_arrival_unit_price_non_negative",
        "slaughter_processings",
        "arrival_unit_price IS NULL OR arrival_unit_price >= 0",
    )

    # 8. Drop slaughter_arrivals table (no more FKs point to it)
    op.execute("DROP INDEX IF EXISTS ix_slaughter_arrivals_chick_arrival_id")
    op.execute("DROP INDEX IF EXISTS ix_slaughter_arrivals_supplier_client_id")
    op.execute("DROP INDEX IF EXISTS ix_slaughter_arrivals_poultry_type_id")
    op.execute("DROP INDEX IF EXISTS ix_slaughter_arrivals_organization_id")
    op.execute("DROP INDEX IF EXISTS ix_slaughter_arrivals_id")
    op.execute("DROP INDEX IF EXISTS ix_slaughter_arrivals_department_id")
    op.execute("DROP INDEX IF EXISTS ix_slaughter_arrivals_arrived_on")
    op.execute("DROP TABLE IF EXISTS slaughter_arrivals")

    # 9. Remove workspace_resources + permissions for slaughter-arrivals
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code LIKE 'slaughter_arrival.%')"
    )
    op.execute("DELETE FROM permissions WHERE code LIKE 'slaughter_arrival.%'")
    op.execute("DELETE FROM workspace_resources WHERE key = 'slaughter-arrivals'")


def downgrade() -> None:
    # Recreate slaughter_arrivals as a minimal skeleton (data loss is accepted)
    op.create_table(
        "slaughter_arrivals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            sa.UUID(),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "poultry_type_id",
            sa.UUID(),
            sa.ForeignKey("poultry_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "supplier_client_id",
            sa.UUID(),
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "chick_arrival_id",
            sa.UUID(),
            sa.ForeignKey("chick_arrivals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("arrived_on", sa.Date(), nullable=False),
        sa.Column("birds_count", sa.Integer(), nullable=False),
        sa.Column("average_weight_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="UZS"),
        sa.Column("invoice_no", sa.String(120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.CheckConstraint("birds_count >= 0", name="ck_slaughter_arrival_birds_count_non_negative"),
        sa.CheckConstraint(
            "average_weight_kg IS NULL OR average_weight_kg >= 0",
            name="ck_slaughter_arrival_avg_weight_non_negative",
        ),
        sa.CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_slaughter_arrival_unit_price_non_negative",
        ),
    )
    op.create_index("ix_slaughter_arrivals_arrived_on", "slaughter_arrivals", ["arrived_on"])
    op.create_index("ix_slaughter_arrivals_department_id", "slaughter_arrivals", ["department_id"])
    op.create_index("ix_slaughter_arrivals_organization_id", "slaughter_arrivals", ["organization_id"])
    op.create_index("ix_slaughter_arrivals_poultry_type_id", "slaughter_arrivals", ["poultry_type_id"])
    op.create_index(
        "ix_slaughter_arrivals_supplier_client_id",
        "slaughter_arrivals",
        ["supplier_client_id"],
    )
    op.create_index(
        "ix_slaughter_arrivals_chick_arrival_id",
        "slaughter_arrivals",
        ["chick_arrival_id"],
    )

    # Drop new check constraints / FKs / indexes on processings
    op.drop_constraint(
        "ck_slaughter_processing_arrival_unit_price_non_negative",
        "slaughter_processings",
        type_="check",
    )
    op.drop_constraint(
        "ck_slaughter_processing_arrival_total_weight_non_negative",
        "slaughter_processings",
        type_="check",
    )
    op.drop_constraint(
        "ck_slaughter_processing_processed_not_exceed_received",
        "slaughter_processings",
        type_="check",
    )
    op.drop_constraint(
        "ck_slaughter_processing_birds_received_non_negative",
        "slaughter_processings",
        type_="check",
    )
    op.drop_constraint(
        "ck_slaughter_processing_source_exactly_one",
        "slaughter_processings",
        type_="check",
    )
    op.drop_constraint(
        "ck_slaughter_processing_source_type",
        "slaughter_processings",
        type_="check",
    )
    op.drop_constraint(
        "fk_slaughter_processings_supplier_client_id",
        "slaughter_processings",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_slaughter_processings_factory_shipment_id",
        "slaughter_processings",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_slaughter_processings_arrived_on",
        table_name="slaughter_processings",
    )
    op.drop_index(
        "ix_slaughter_processings_supplier_client_id",
        table_name="slaughter_processings",
    )
    op.drop_index(
        "ix_slaughter_processings_factory_shipment_id",
        table_name="slaughter_processings",
    )
    op.drop_index(
        "ix_slaughter_processings_source_type",
        table_name="slaughter_processings",
    )

    # Re-add arrival_id (nullable — best-effort restore)
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_slaughter_processings_arrival_id",
        "slaughter_processings",
        "slaughter_arrivals",
        ["arrival_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_slaughter_processings_arrival_id",
        "slaughter_processings",
        ["arrival_id"],
    )
    op.create_unique_constraint(
        "uq_slaughter_processing_arrival_date",
        "slaughter_processings",
        ["arrival_id", "processed_on"],
    )

    # Drop new hybrid columns
    op.drop_column("slaughter_processings", "arrival_invoice_no")
    op.drop_column("slaughter_processings", "arrival_currency")
    op.drop_column("slaughter_processings", "arrival_unit_price")
    op.drop_column("slaughter_processings", "arrival_total_weight_kg")
    op.drop_column("slaughter_processings", "birds_received")
    op.drop_column("slaughter_processings", "arrived_on")
    op.drop_column("slaughter_processings", "supplier_client_id")
    op.drop_column("slaughter_processings", "factory_shipment_id")
    op.drop_column("slaughter_processings", "source_type")
