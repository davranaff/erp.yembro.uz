# ADR 0001 — Row-level scope isolation

- **Status:** Proposed (awaiting approval)
- **Date:** 2026-04-19
- **Supersedes:** —
- **Related:** `SCOPE_AUDIT_REPORT.md`, `AGENT_PROMPT_SCOPE_ISOLATION.md`, `MODULES_REVIEW.md` (S2)

## Context

Yembro ERP today enforces row-level access via `BaseService._scope_filters_to_actor` and `_ensure_actor_can_access_entity` ([backend/app/services/base.py:580-663](../../backend/app/services/base.py#L580)). Both rely on `CurrentActor.department_id` — **a single value** — and filter only by `organization_id` + `department_id`. Warehouse scope exists only inside `StockLedgerService` and is bypassed by the CRUD router. Dashboard builders ignore department/warehouse entirely.

Consequences: finance clerks see all org cash accounts, dashboard aggregates leak cross-department, warehouse staff at site A see stock movements at site B, and users who legitimately need access to several departments cannot be modelled at all.

## Decision

We adopt **Option A (assignment table) + Option C (hierarchical expansion) hybrid**, evolving the existing dept-scope code rather than replacing it.

### Data model

1. **Keep `Employee.department_id`** as user's *home department*. No migration on existing rows.
2. **New table `user_scope_assignment`** — explicit extra access:

   ```
   user_scope_assignment(
     id UUID PK,
     organization_id UUID FK -> organizations(id),
     user_id UUID FK -> users(id),
     scope_type TEXT CHECK IN ('department','warehouse'),
     scope_id UUID,           -- FK resolved by scope_type
     permission_prefix TEXT NULL,  -- e.g. 'finance.cash_account' to scope one permission
     created_at / updated_at / created_by / updated_by
     UNIQUE (user_id, scope_type, scope_id, permission_prefix)
   )
   ```

3. **Effective scope** (computed once per request, cached in FastAPI request state):

   ```
   allowed_department_ids =
       { employee.department_id }                                    -- home dept
     ∪ { a.scope_id for a in assignments(user, 'department') }       -- explicit grants
     ∪ descendants(any of the above via Department.parent_department_id)  -- tree expansion
   allowed_warehouse_ids =
       { w.id for w in warehouses(department_id ∈ allowed_departments) }  -- inherited
     ∪ { a.scope_id for a in assignments(user, 'warehouse') }        -- explicit grants
   is_org_admin = role ∈ {super_admin, admin}
   ```

4. **Org-admin bypass:** if `is_org_admin` → scope returns `None` (no `WHERE` added). Matches existing `_actor_bypasses_*` semantics.

### Why hybrid A+C (not B, not pure A, not pure C)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| A (assignment table) | Per-permission grants, extensible, migration-friendly | +1 JOIN per request | Used as primary |
| B (ARRAY columns on Employee) | Simple, fast | No per-permission, breaks existing `Employee` API, array mutations in ORM are painful | Rejected |
| C (hierarchical from `parent_department_id`) | Elegant for nested organisations | Doesn't cover «extra access to an unrelated department» | Used as supplement |
| **Hybrid A+C** | Covers hierarchy naturally (users who head parent dept see children) + allows ad-hoc grants | Extra helper to expand tree | **Chosen** |

The hybrid requires **zero change** to existing org-admin / department-lead behavior because the computation includes `Employee.department_id` as a grant and expands hierarchy.

### Mechanism

1. **`backend/app/core/scope.py` — new module:**

   ```python
   @dataclass(frozen=True)
   class UserScope:
       allowed_department_ids: frozenset[str] | None  # None = bypass
       allowed_warehouse_ids: frozenset[str] | None
       is_org_admin: bool

       def apply(self, stmt: Select, model: type[Base]) -> Select:
           if self.is_org_admin: return stmt
           if self.allowed_department_ids is not None and hasattr(model, "department_id"):
               stmt = stmt.where(model.department_id.in_(self.allowed_department_ids))
           if self.allowed_warehouse_ids is not None and hasattr(model, "warehouse_id"):
               stmt = stmt.where(model.warehouse_id.in_(self.allowed_warehouse_ids))
           return stmt

       def can_access(self, *, department_id: str | None = None,
                            warehouse_id: str | None = None) -> bool: ...
   ```

2. **FastAPI dependency `current_scope(actor, db) -> UserScope`** — memoised per request (stored in `request.state.scope`).

3. **`BaseService` extension:**
   - `_scope_filters_to_actor` reads `actor.allowed_department_ids` + `allowed_warehouse_ids` (lists) instead of single `department_id`. Legacy single-dept path remains as fallback when lists are empty → **zero breakage for existing tests**.
   - New `_uses_warehouse_scope()` hook, default `False`; services with `warehouse_id` override to `True`.

4. **`CurrentActor` extension:** add `allowed_department_ids: frozenset[str]`, `allowed_warehouse_ids: frozenset[str]`, `is_org_admin: bool`. Populated in auth dependency.

### Frontend contract

**`GET /api/v1/auth/me`** (new or extended):

```json
{
  "user_id": "...",
  "organization_id": "...",
  "employee_id": "...",
  "home_department_id": "...",
  "allowed_department_ids": ["...", "..."],
  "allowed_warehouse_ids": ["..."],
  "is_org_admin": false,
  "permissions": [...],
  "roles": [...]
}
```

Frontend stores these in `AuthSession` ([frontend/src/shared/auth/types.ts](../../frontend/src/shared/auth/types.ts)) and exposes via `<ScopeProvider>` mounted in `RootLayout`. Selectors (`useWarehouseMovement`, cash account picker, department picker) read from `ScopeProvider` and pass allowed-list as query params — backend filter is authoritative, frontend filter is defense-in-depth.

### Special cases

- **Transfer between warehouses:** both `source_warehouse_id` and `destination_warehouse_id` must be in `allowed_warehouse_ids`. Enforced in `StockLedgerService.transfer` and in the frontend transfer form (show only pairs from allowed list).
- **Dashboard executive widgets:** gated by `is_org_admin` on both backend (omit payload) and frontend (explicit role gate). Non-admin sees aggregations over their scope only.
- **Feature flag:** `ENABLE_ROW_LEVEL_SCOPE` in [backend/app/core/config.py](../../backend/app/core/config.py). When `False`, `UserScope.apply` returns stmt unchanged and lists are empty → old single-dept behavior preserved. Default `False` in first deploy; flip to `True` after fixtures are seeded.
- **Org-admin / super-admin:** `is_org_admin=True` → `UserScope` carries `None` allow-lists → no WHERE added. Matches today's bypass.
- **Backwards compatibility:** users without any `user_scope_assignment` rows have `allowed_department_ids = {home_dept} ∪ descendants(home_dept)` — equivalent to current behavior plus free-of-charge hierarchy expansion (no regression, slight widening for department heads, which is desirable).

### Response codes

- Foreign-scope read on list endpoint → **row omitted** (silently filtered).
- Foreign-scope read on detail endpoint → **404** (not 403 — do not leak existence).
- Foreign-scope write → **404** (same rationale).
- Transfer with one warehouse out of scope → **403** (error is relational, not about a single object).

### What moves, what stays

**Stays:**
- Existing `BaseService` hooks (`_uses_department_scope`, bypass flags, `_ensure_actor_can_access_entity` signature).
- `PRIVILEGED_SCOPE_ROLES` in `inventory.py` — will reference `is_org_admin` instead of re-checking role strings.
- Existing `Employee.department_id` (kept as home dept).

**Moves:**
- `_scope_filters_to_actor` body — rewritten to use `UserScope`.
- `StockLedgerService._resolve_scope` — delegates to `UserScope.apply`, removing duplication.
- Dashboard builders — single decorator `@scoped(Model)` adds WHERE.

## Consequences

### Positive
- One mechanism for dept + warehouse + future scope types.
- Backward compatible (flag + legacy-fallback in filter code).
- Hierarchical access «for free» from existing `parent_department_id` tree.
- Per-permission grants possible via `user_scope_assignment.permission_prefix` — enables narrow grants like «accountant sees cash accounts of dept A only, not full dept».

### Negative
- +1 JOIN (or +1 cached fetch) per request for assignment lookup — mitigated by request-scoped cache.
- All services with `warehouse_id` must opt in via `_uses_warehouse_scope()` — explicit but mechanical.
- Dashboard queries need rewriting to pass through `UserScope.apply` — touches 18 builders.

### Risks and mitigations
| Risk | Mitigation |
|---|---|
| Silent over-filter (users lose access) | Legacy fallback: empty allow-lists → current behavior. Integration tests per service. |
| Dashboard performance regression | Index `(organization_id, department_id)` already exists on most tables; add `(warehouse_id)` where missing. |
| 404 vs 403 confusion | Documented in API style guide. |
| Assignment table bloat | Rare rows (manual grants); no concern at realistic org sizes. |

## Implementation plan (for Phase 4)

1. Alembic migration `g0a1b2c3d4e5_user_scope_assignment.py` — creates table, adds indexes.
2. `backend/app/core/scope.py` — `UserScope` + dep + tests.
3. Extend `CurrentActor` + auth dep to populate allow-lists.
4. Extend `BaseService` — lists-aware filter and access check, feature flag.
5. Enable `_uses_warehouse_scope()` on: `StockMovementService`, `StockReorderLevelService`, `StockTakeService`, `MedicineBatchService`. `MedicineConsumptionService` inherits via `batch_id`.
6. Dashboard pass — add `apply_scope(stmt, Model)` in each builder.
7. `/auth/me` endpoint extension.
8. Frontend: `AuthSession` + `ScopeProvider` + hook updates.
9. Fixtures: seed `is_org_admin` on admin role.
10. Tests: unit (UserScope), integration (per service), E2E (two-user isolation).

Per-domain sub-agent ownership mapping matches `AGENT_PROMPT_SCOPE_ISOLATION.md § EXECUTION STRATEGY`.

## Open questions

1. Does `/api/v1/auth/me` exist today? (TODO verify in [backend/app/api/v1/auth.py](../../backend/app/api/v1/auth.py))
2. Should `permission_prefix` grants ship in v1 or v2? **Recommendation:** v2 — keep v1 simple (scope only).
3. Assignment grant UI — admin-only page or CLI first? **Recommendation:** CLI/fixtures in v1, UI in v2.

## Approval checkpoint

Before Phase 4 begins, user confirms:
- [ ] Data model: Hybrid A+C chosen (assignment table + hierarchy expansion)?
- [ ] Feature flag `ENABLE_ROW_LEVEL_SCOPE`, default `False` in first deploy — OK?
- [ ] `404` on foreign-scope detail read (not `403`) — OK?
- [ ] `permission_prefix` deferred to v2 — OK?
- [ ] Implementation order (backend → frontend, P0 domains first) — OK?
