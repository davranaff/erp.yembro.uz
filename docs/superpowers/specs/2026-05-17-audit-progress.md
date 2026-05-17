# Audit progress — feed/vet/slaughter hardening

**Goal:** прод-готовность модулей feed/vet/slaughter. Касса и склады не должны врать.

**Updated:** 2026-05-17 (running)

## Strategy: 5 циклов аудита

Каждый цикл — 3 параллельных Explore subagent'а (по одному на feed/vet/slaughter), сфокусированных на классе багов.

- **Цикл 1: Race conditions + concurrency** (запущен, отчёты ниже)
- **Цикл 2: Negative balances + overspend** — pending
- **Цикл 3: Idempotency + double-submit** — pending
- **Цикл 4: Partial-failure atomicity** — pending
- **Цикл 5: Data validation + cross-org + FK protection** — pending

## Правила автономной работы (для scheduled routine)

- **НЕ пушить** — никаких `git push`.
- **НЕ amend** существующих коммитов — только новые.
- **НЕ удалять** prod-данные / dump-файлы / .env.
- **НЕ запускать** migrations и не менять модели — только сервисы/views/тесты/admin.
- **Каждый коммит** атомарный и описанный.
- **pytest падения на main** не фиксить (известные предсуществующие, см. `test_opening_balance` и др.).
- После каждого фикса — обновить этот файл (Completed / Deferred).
- Если все 5 циклов пройдены — делать ещё проход с фокусом на ещё не покрытые сервисы.

## Цикл 1 — Race conditions: findings

### FEED (15+ findings)

| Pri | File:line | Issue | Fix |
|-----|-----------|-------|-----|
| ✅ P0 | `feed/services/package_feed_batch.py:163-167` | ~~Двойной `select_for_update().get()` → второй `.get()` без lock теряет блокировку~~ | Fixed in `479c2ca` |
| ✅ P0 | `feed/services/shrinkage_runner.py:398` | ~~`FeedLotShrinkageState.objects.create()` без guard~~ | Fixed in `479c2ca` |
| ✅ P0 | `feed/services/sell_feed_bag.py:180-189` | ~~Lock теряется после `confirm_sale()` + `refresh_from_db()`~~ | Fixed in `216d0fa` |
| 🟡 P1 | `feed/services/package_feed_batch.py:222-230` | `_empty_bag_stock()` SELECT SUM без lock → может уйти в минус | `select_for_update` на packaging SKU |
| 🟡 P1 | `feed/services/copy_components.py:85-90` | FIFO выбор партии без lock → 2 задания могут зацепиться за одну | `select_for_update` на выбранный batch |
| 🟡 P1 | `feed/services/quality.py:39,85-88` | Status race APPROVED vs REJECTED parallel | re-check status after lock |
| 🟢 P2 | `feed/views.py:237-268,270-303,496-527` | release_quarantine / reject_quarantine / approve_passport без `select_for_update` | view-level lock |
| 🟢 P2 | `feed/views.py:322-345` | perform_create + copy_components на double-submit | idempotency key |

### VET (3 critical)

| Pri | File:line | Issue | Fix |
|-----|-----------|-------|-----|
| ✅ P0 | `vet/services/receive_accessory.py:79-83` | ~~WAC race — двойной select_related теряет lock~~ | Fixed in `479c2ca` |
| ✅ P0 | `vet/services/apply_treatment.py:166-185` | ~~Recall vs apply parallel → двойной write-off~~ | Fixed in `216d0fa` (explicit lock + status check) |
| ✅ P0 | `vet/services/apply_treatment.py:152-160` | ~~Idempotency check `if existing_je` — check-then-act~~ | Fixed in `216d0fa` (select_for_update) |
| 🟡 P1 | `vet/views_public.py:228-250` | Public scanner endpoint: double-submit на /sell/ может создать 2 SaleOrder | idempotency_key field + Redis cache |

### SLAUGHTER (3 fixes)

| Pri | File:line | Issue | Fix |
|-----|-----------|-------|-----|
| 🟡 P1 | `slaughter/services/reverse_shift.py:65-194` | source_batch лочится поздно (line 194) — между check status и save batch.state race | Lock source_batch сразу после shift |
| 🟡 P1 | `slaughter/views.py:71-91` | get_object без lock → 2 concurrent POST на post_shift могут пройти первые проверки | `queryset.select_for_update().get(pk)` в view |
| 🟢 P2 | `slaughter/services/post_shift.py:237-247` | SlaughterQualityCheck filter без lock | `select_for_update()` на QC |

## Completed fixes (приоритет P0 закроем первыми)

| SHA | Issue | Cycle |
|-----|-------|-------|
| `479c2ca` | Feed package_feed_batch: lock lost between two `.get()` → fix to single `select_for_update(of="self").select_related()` | C1 P0 |
| `479c2ca` | Feed shrinkage_runner: `objects.create()` → `get_or_create()` for FeedLotShrinkageState | C1 P0 |
| `479c2ca` | Vet receive_accessory: same double-`.get()` WAC race → single select_for_update(of=self).select_related() | C1 P0 |
| `216d0fa` | Vet apply_treatment: idempotency JE-lookup with `select_for_update()` | C1 P0 |
| `216d0fa` | Vet apply_treatment: stock_batch explicit lock before status/qty check (recall race) | C1 P0 |
| `216d0fa` | Feed sell_feed_bag_lot: re-lock bag_lot after confirm_sale before DEPLETED flip | C1 P0 |
| `3a0be72` | Feed copy_components: FIFO source-batch lookup with select_for_update | C1 P1 |
| `3a0be72` | Slaughter reverse_shift: source_batch lock early (after shift lock) | C1 P1 |
| `3a0be72` | Slaughter post_shift: SlaughterQualityCheck select_for_update | C1 P1 |
| `3a0be72` | Feed views: release/reject_quarantine + approve/reject_passport view-level lock | C1 P1 |
| `2e50373` | Warehouses create_manual_movement: balance guard against overspend on OUTGOING/WRITE_OFF/SHRINKAGE/TRANSFER | C2 P0 |
| `2e50373` | Warehouses balance.compute_warehouse_balance_for_sku: include SHRINKAGE in out_qty | C2 P0 |
| `2e50373` | Feed shrinkage_runner._decrement_lot_current_quantity: floor loss to current_quantity, early-return on 0 | C2 P0 |
| `972ca60` | Transfers _accept_poultry_transfer: lock batch + guard current_quantity ≥ transfer.quantity | C2 P1 |
| `972ca60` | Vet cancel_treatment: lock VetStockBatch + reject overshoot (current + dose > quantity) | C2 P1 |
| `269c1aa` | Feed/Vet admin: readonly_fields on quantity/current_quantity/bags_remaining/unit_cost on stock entities | C2 P2 |

## Deferred (need design discussion)

- Public vet-scanner idempotency_key — нужен Redis или новая таблица. Не делать автоматически.
- DB-level CHECK constraint `current_quantity >= 0` — миграция, требует решения.
- VetTreatmentLog `journal_entry_id` unique field — миграция, требует решения.

## Цикл 2 — Negative balances: completed

### Closed
- Manual stock movement overspend (P0) — теперь нельзя списать с пустого склада через API
- Balance aggregation: SHRINKAGE учтён (P0) — счета на проде больше не «лежат» сотни кг усушки
- Shrinkage runner: loss floored to current_quantity (P0) — больше нет негативного остатка
- Transfers poultry: guard на batch.current_quantity (P1)
- Vet cancel: overshoot guard + lock (P1)
- Admin readonly на counter-полях стоков (P2)

### Deferred / not changed
- execute_task TOCTOU: уже закрыт через row-lock в Cycle 1 (`d290291` + `479c2ca`), агент не учёл fix
- Decimal precision mismatch dose_quantity (4) vs current_quantity (3): требует data migration на изменение precision — design discussion
- Views frontend: показ ⚠️ при negative balance — frontend задача, делать отдельно

## Цикл 3 — Idempotency: pending

## Цикл 4 — Atomicity: pending

## Цикл 5 — Validation: pending

## Commit log

| SHA | Issue | Cycle |
|-----|-------|-------|
| (pending) | | |
