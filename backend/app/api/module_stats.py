from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends

from app.api.deps import db_dependency, get_current_actor
from app.db.pool import Database
from app.schemas.stats import ModuleStatsItemSchema, ModuleStatsResponseSchema


@dataclass(frozen=True, slots=True)
class ModuleStatsTable:
    key: str
    label: str
    table: str


async def _get_table_total(db: Database, table: str) -> int:
    row = await db.fetchrow(f'SELECT COUNT(*) AS total FROM "{table}"')
    return int(row["total"]) if row is not None else 0


def register_module_stats_route(
    router: APIRouter,
    *,
    module: str,
    label: str,
    tables: tuple[ModuleStatsTable, ...],
) -> None:
    @router.get(
        "/stats",
        response_model=ModuleStatsResponseSchema,
        dependencies=[Depends(get_current_actor)],
        name=f"{module}_stats",
        operation_id=f"get_{module}_stats",
    )
    async def get_module_stats(db: Database = Depends(db_dependency)) -> ModuleStatsResponseSchema:
        items: list[ModuleStatsItemSchema] = []
        total = 0

        for table in tables:
            table_total = await _get_table_total(db, table.table)
            total += table_total
            items.append(ModuleStatsItemSchema(key=table.key, label=table.label, total=table_total))

        return ModuleStatsResponseSchema(module=module, label=label, total=total, items=items)
