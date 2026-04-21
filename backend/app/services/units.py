"""Helpers for resolving free-form unit codes to measurement_units FK."""

from __future__ import annotations

from app.core.exceptions import ValidationError


_UNIT_ALIASES = {"pcs": "dona", "bosh": "dona", "l": "litr", "kilogram": "kg", "kilogramm": "kg"}


async def resolve_measurement_unit_id(db, organization_id: str, unit_code: str | None) -> str:
    """Return measurement_units.id for the given organization + unit code.

    Accepts common aliases (pcs → dona, l → litr). Falls back to 'kg' for
    the org if the requested code is not found. Raises ValidationError if
    the organization has no measurement_units at all.
    """
    code = (unit_code or "kg").strip().lower()
    code = _UNIT_ALIASES.get(code, code)
    row = await db.fetchrow(
        "SELECT id FROM measurement_units WHERE organization_id = $1 AND code = $2 LIMIT 1",
        organization_id,
        code,
    )
    if row is None:
        row = await db.fetchrow(
            "SELECT id FROM measurement_units WHERE organization_id = $1 AND code = 'kg' LIMIT 1",
            organization_id,
        )
    if row is None:
        raise ValidationError(f"measurement_unit '{code}' not found for organization")
    return str(row["id"])
