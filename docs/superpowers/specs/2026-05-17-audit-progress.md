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
| 🔴 P0 | `feed/services/package_feed_batch.py:163-167` | Двойной `select_for_update().get()` → второй `.get()` без lock теряет блокировку | Объединить в один `select_for_update().select_related().get()` |
| 🔴 P0 | `feed/services/shrinkage_runner.py:398` | `FeedLotShrinkageState.objects.create()` без guard → параллельный cron ловит dup-key | `get_or_create()` |
| 🔴 P0 | `feed/services/sell_feed_bag.py:180-189` | Lock теряется после `confirm_sale()` + `refresh_from_db()` → status flip может перезаписать | Повторный `select_for_update` после confirm |
| 🟡 P1 | `feed/services/package_feed_batch.py:222-230` | `_empty_bag_stock()` SELECT SUM без lock → может уйти в минус | `select_for_update` на packaging SKU |
| 🟡 P1 | `feed/services/copy_components.py:85-90` | FIFO выбор партии без lock → 2 задания могут зацепиться за одну | `select_for_update` на выбранный batch |
| 🟡 P1 | `feed/services/quality.py:39,85-88` | Status race APPROVED vs REJECTED parallel | re-check status after lock |
| 🟢 P2 | `feed/views.py:237-268,270-303,496-527` | release_quarantine / reject_quarantine / approve_passport без `select_for_update` | view-level lock |
| 🟢 P2 | `feed/views.py:322-345` | perform_create + copy_components на double-submit | idempotency key |

### VET (3 critical)

| Pri | File:line | Issue | Fix |
|-----|-----------|-------|-----|
| 🔴 P0 | `vet/services/receive_accessory.py:79-83` | WAC race — двойной select_related теряет lock → weighted-avg cost ломается параллельным receive | Объединить `select_for_update().select_related()` |
| 🔴 P0 | `vet/services/apply_treatment.py:166-185` | Recall vs apply parallel → двойной write-off возможен | `refresh_from_db(fields=["status"])` после lock + abort if not AVAILABLE |
| 🔴 P0 | `vet/services/apply_treatment.py:152-160` | Idempotency check `if existing_je` — check-then-act, не атомарно | `JournalEntry.objects.select_for_update()` lookup |
| 🟡 P1 | `vet/views_public.py:228-250` | Public scanner endpoint: double-submit на /sell/ может создать 2 SaleOrder | idempotency_key field + Redis cache |

### SLAUGHTER (3 fixes)

| Pri | File:line | Issue | Fix |
|-----|-----------|-------|-----|
| 🟡 P1 | `slaughter/services/reverse_shift.py:65-194` | source_batch лочится поздно (line 194) — между check status и save batch.state race | Lock source_batch сразу после shift |
| 🟡 P1 | `slaughter/views.py:71-91` | get_object без lock → 2 concurrent POST на post_shift могут пройти первые проверки | `queryset.select_for_update().get(pk)` в view |
| 🟢 P2 | `slaughter/services/post_shift.py:237-247` | SlaughterQualityCheck filter без lock | `select_for_update()` на QC |

## Completed fixes (приоритет P0 закроем первыми)

(заполнять по мере выполнения)

## Deferred (need design discussion)

- Public vet-scanner idempotency_key — нужен Redis или новая таблица. Не делать автоматически.
- DB-level CHECK constraint `current_quantity >= 0` — миграция, требует решения.
- VetTreatmentLog `journal_entry_id` unique field — миграция, требует решения.

## Цикл 2 — Negative balances: pending

## Цикл 3 — Idempotency: pending

## Цикл 4 — Atomicity: pending

## Цикл 5 — Validation: pending

## Commit log

| SHA | Issue | Cycle |
|-----|-------|-------|
| (pending) | | |
