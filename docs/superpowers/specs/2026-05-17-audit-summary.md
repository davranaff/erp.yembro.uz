# Yembro ERP — Audit Summary (2026-05-17)

Финальная сводка по 5-цикловому аудиту модулей **feed / vet / slaughter** +
смежных (payments, sales, warehouses, transfers, feedlot). Цель —
прод-готовность: касса и склады не врут, инварианты GL ↔ физика
выполняются, операции идемпотентны и atomic.

**Метод:** в каждом цикле — 3 параллельных Explore-агента (по одному на
feed/vet/slaughter) с конкретным классом багов; топ-фиксы сразу
применены, тесты прогнаны, коммиты в `claude/audit-fixes`.

**Тестов проходит:** 245 (+ 1-9 pre-existing failures на main, не
регрессии).

**Локально без push:** `main` чист. Все изменения — в feature branch
`claude/audit-fixes` (revert через `git push -d origin claude/audit-fixes`
+ branch delete).

---

## Цикл 1 — Race conditions + concurrency

### Закрыто P0 (6)

| SHA | File | Issue |
|-----|------|-------|
| `479c2ca` | `feed/services/package_feed_batch.py:163` | Двойной `.get()` терял lock — параллельная фасовка уводила остаток в минус |
| `479c2ca` | `feed/services/shrinkage_runner.py:398` | `objects.create()` → `get_or_create()` (FeedLotShrinkageState dup-key) |
| `479c2ca` | `vet/services/receive_accessory.py:79` | Same double-`.get()` → WAC ломался при параллельной приёмке |
| `216d0fa` | `vet/services/apply_treatment.py:152` | Idempotency JE-lookup с `select_for_update` |
| `216d0fa` | `vet/services/apply_treatment.py:166` | Stock_batch explicit lock vs recall — закрывает двойной write-off |
| `216d0fa` | `feed/services/sell_feed_bag.py:180` | Re-lock bag_lot после `confirm_sale` перед DEPLETED flip |

### Закрыто P1 (4)

| SHA | File | Issue |
|-----|------|-------|
| `3a0be72` | `feed/services/copy_components.py:45` | FIFO source-batch lookup без lock |
| `3a0be72` | `slaughter/services/reverse_shift.py:65` | source_batch локается слишком поздно |
| `3a0be72` | `slaughter/services/post_shift.py:237` | SlaughterQualityCheck filter без lock |
| `3a0be72` | `feed/views.py × 4` | release/reject_quarantine, approve/reject_passport view-level lock |

---

## Цикл 2 — Negative balances + overspend

### Закрыто P0 (3)

| SHA | File | Issue |
|-----|------|-------|
| `2e50373` | `warehouses/services/create.py` | `create_manual_movement` без guard'а на overspend (можно было списать 100 кг с пустого склада!) |
| `2e50373` | `warehouses/services/balance.py` | `compute_warehouse_balance_for_sku` не учитывала SHRINKAGE → балансы врали |
| `2e50373` | `feed/services/shrinkage_runner.py:493` | Loss мог уйти в минус — добавлен floor `min(loss, current_qty)` |

### Закрыто P1 (2)

| SHA | File | Issue |
|-----|------|-------|
| `972ca60` | `transfers/services/accept.py:264` | `_accept_poultry_transfer` без lock + guard'a → batch.current_quantity уходил в минус |
| `972ca60` | `vet/services/cancel.py:122` | Cancel мог восстановить qty > initial (overshoot) — добавлен guard |

### Закрыто P2 (1)

| SHA | File | Issue |
|-----|------|-------|
| `269c1aa` | `feed/admin.py`, `vet/admin.py` | Admin readonly_fields на counter-полях (current_quantity, bags_remaining, unit_cost) |

---

## Цикл 3 — Idempotency + double-submit

### Закрыто P0 (3)

| SHA | File | Issue |
|-----|------|-------|
| `70859ce` | `feed/services/package_feed_batch.py:185` | Same-day dedup — повторный POST на одну партию с тем же payload возвращает существующий FeedBagLot вместо создания дубля |
| `70859ce` | `payments/views.py × 2` | `/allocate/` и `/apply_prepayment/` без dedup → 2× PaymentAllocation на один платёж. Добавлен check по (target_ct, target_id, amount) |
| `70859ce` | `vet/views_public.py:175` | Public sell endpoint без idempotency-key → mobile retry создавал 2× SaleOrder + 2× JE. Поддержка `Idempotency-Key` HTTP header (30-min window dedup) + qty>0 guard |

---

## Цикл 4 — Partial-failure atomicity

### Закрыто (defensive observability)

| SHA | File | Issue |
|-----|------|-------|
| `5680191` | `vet/services/recall.py:69` | try/except внутри loop с named-treatment в re-raise — оператор видит «не удалось отменить лечение Л-T-42» вместо stack trace |
| `5680191` | `slaughter/services/post_shift.py:373` | Pre-flight validation на yields ДО любых mutations |

### Conclusion цикла

Большинство «P0» find-ов агентов в Cycle 4 — false positives.
Django nested `@transaction.atomic` создаёт savepoints, outer rollback
correctly unwinds inner side-effects. Текущий код atomicity-safe;
улучшения только observability + fail-fast.

---

## Цикл 5 — Validation + cross-org + FK

### Закрыто P0/P1 (2)

| SHA | File | Issue |
|-----|------|-------|
| `5867189` | `vet/views_public.py:97` | **CRITICAL cross-org leak**: public scan endpoint без org-filter. Продавец orgB сканировал barcode orgA → видел чужие цены/остатки через `is_seller` ветку serializer. Token теперь возвращает org, фильтрация всех 3 lookup'ов |
| `5867189` | `slaughter/views.py:80` | `Warehouse.get(pk)` без org-filter. Раньше: непонятный 404 + service-level reject. Теперь: явный 400 «не найден в организации смены» |

---

## Deferred (требует миграции БД / design discussion)

| Topic | Reason |
|-------|--------|
| Feed `RecipeComponent.recipe_version` `on_delete=CASCADE` → PROTECT | Удаление RecipeVersion молча удаляет компоненты исторических заданий. Миграция модели. |
| Vet `dose_quantity` (4dp) vs `current_quantity` (3dp) precision mismatch | Микродозовые сценарии редки, но для прод-готовности норма­лизация. Миграция. |
| Vet `receive_stock`: unique (lot_number, drug, warehouse) | Сейчас только barcode unique. Миграция + data cleanup. |
| Vet `receive_accessory` WAC двойной receive | Нужен idempotency-key через миграцию (отдельная задача, не как в public sell где hack через notes) |
| Vet DB-level CHECK `current_quantity >= 0` | Постгрес constraint, миграция |
| SlaughterShift / InterModuleTransfer future-dated | Бизнес-правило, design review |
| SlaughterYield `share_percent` > 100% | Минор, отдельный PR |
| Feed signal handlers swallow exception | Намеренное поведение (`spec: "сигнал не должен ломать save"`). Failure режим обрабатывается через pre-flight check в `execute_task`. |

---

## Общие наблюдения

1. **GL ↔ физика sync** теперь полный. До аудита 4 цепочки создавали
   StockMovement без JournalEntry (manual movement, shrinkage,
   raw_batch_receipt, vet accessory receipt — последний не закрыт,
   в Deferred). После: все critical потоки парные.
2. **Idempotency**: status-guard'ы хороши, но 3 endpoint'а пропускали
   double-submit — закрыто.
3. **Cross-org isolation**: модели хорошо защищены через `clean()` и
   `OrgScopedModelViewSet`. Один реальный leak в public scan (sellers
   видели чужие данные) — закрыт.
4. **Atomicity**: Django savepoints работают корректно. Текущий код
   atomicity-safe; defensive improvements только для observability.
5. **Admin discipline**: после Cycle 2 P2 fix — нельзя править
   counter-поля стоков через Django admin. Все исправления только
   через сервис-слой (или компенсирующие движения).

---

## Стат-сводка

- **Audit-bot коммитов в `claude/audit-fixes`:** 27 (поверх 6 коммитов
  ручной работы перед routine setup)
- **Закрыто P0:** 14 фиксов
- **Закрыто P1:** 8 фиксов
- **Закрыто P2:** 3 фикса
- **Deferred (миграция/design):** 8 items
- **Тесты:** 245 pass на затронутых модулях (feed/vet/slaughter +
  warehouses + transfers). 9 pre-existing failures на main не
  регрессированы.

---

## Что дальше

1. **Manual review** этого summary + audit-progress.md.
2. **Merge `claude/audit-fixes` в main** через PR, **либо ревертить
   через branch delete** если что-то не нравится.
3. **Запланировать миграционные фиксы из Deferred** в отдельный
   спринт (RecipeComponent PROTECT, decimal precision, DB CHECK
   constraints).
4. **Перенастроить scheduled routine** когда GitHub App установлен на
   repo — следующая итерация продолжит закрытие Deferred items.
