from __future__ import annotations

from typing import Any

import pytest

from app.repositories.base import BaseRepository


class _CaptureDb:
    def __init__(self) -> None:
        self.query: str | None = None
        self.args: tuple[Any, ...] = ()

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.query = query
        self.args = args
        return []


class _Repository(BaseRepository[dict[str, Any]]):
    table = "departments"


@pytest.mark.asyncio
async def test_list_offsets_parameter_numbers_after_where_clause() -> None:
    db = _CaptureDb()
    repository = _Repository(db)

    await repository.list(
        filters={"organization_id": "11111111-1111-1111-1111-111111111111"},
        limit=25,
        offset=50,
    )

    assert db.query is not None
    assert 'WHERE "organization_id" = $1 LIMIT $2 OFFSET $3' in db.query
    assert db.args == ("11111111-1111-1111-1111-111111111111", 25, 50)


@pytest.mark.asyncio
async def test_pluck_offsets_parameter_numbers_after_where_clause() -> None:
    db = _CaptureDb()
    repository = _Repository(db)

    await repository.pluck(
        "name",
        filters={"organization_id": "11111111-1111-1111-1111-111111111111"},
        limit=10,
        offset=20,
    )

    assert db.query is not None
    assert 'WHERE "organization_id" = $1 LIMIT $2 OFFSET $3' in db.query
    assert db.args == ("11111111-1111-1111-1111-111111111111", 10, 20)
