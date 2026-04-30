# Анатомия транзакции (F0.6)

**Статус:** актуальная архитектурная договорённость · 2026-04-30

Каждый документ в системе, имеющий финансовый или количественный эффект,
обязан содержать **минимальный набор полей трассировки**. Это требование ТЗ §F0.6.

## Минимальный набор полей

| Поле | Тип | Обязательность | Цель |
|---|---|---|---|
| `operation_date` (или `entry_date`/`date`/`received_date`/`produced_at` — что семантичнее) | Date / DateTime | **Обязательно** | Когда операция произошла в реальности (не путать с `created_at`!) |
| `organization` | FK Organization | **Обязательно** | Multi-tenant изоляция |
| `currency` + `amount_foreign` + `exchange_rate` | FK / Decimal / Decimal | Опциональны | Если операция в иностранной валюте — храним оригинал + курс на дату операции, в `amount_uzs` лежит UZS-эквивалент |
| `source_content_type` + `source_object_id` (GenericForeignKey) | FK ContentType + UUID | **Обязательно для производных** | Откуда документ родился: `purchase`/`sale_order`/`feed_consumption`/`shrinkage_state` и т.д. — для полной трассировки |
| `created_at` / `updated_at` | TimestampedModel mixin | Авто | Когда запись добавлена в БД (для аудита, ≠ дата операции) |
| `created_by` | FK User nullable | Где имеет смысл | Кто внёс запись |

## Где это уже применено

| Модель | `operation_date` | `source` | `currency` |
|---|---|---|---|
| `accounting.JournalEntry` | `entry_date` ✅ | `source_*` GenericFK ✅ | ✅ + `amount_foreign`/`exchange_rate` |
| `warehouses.StockMovement` | `date` ✅ | `source_*` GenericFK ✅ | — (натуральный учёт в кг/шт) |
| `payments.Payment` | `date` ✅ | косвенно через `purchase_order`/`sale_order` FK | ✅ через related объект |
| `purchases.PurchaseOrder` | `date` ✅ | — (это первичный) | ✅ |
| `sales.SaleOrder` | `date` ✅ | — (первичный) | ✅ |
| `feed.RawMaterialBatch` | `received_date` ✅ | через `purchase` FK | ✅ |
| `feed.FeedBatch` | `produced_at` ✅ | через `produced_by_task` FK | — (себестоимость в UZS-эквиваленте) |
| `feedlot.DailyWeighing` / `Mortality` | `date` ✅ | — | — |
| `accounting.CashAdvance` | `issued_date` ✅ | через `issued_payment` FK | — (поддержка валюты — v2) |

## Правила для новых модулей

Когда добавляете **новую таблицу с финансовым/количественным эффектом**:

1. ✅ **Дата операции** — отдельное поле от `created_at`. Имя по семантике: `entry_date`/`received_date`/`shipment_date`/`closed_date`. Тип `DateField` если важен только день, `DateTimeField` если момент.

2. ✅ **Org-scope** — `organization = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT)`.

3. ✅ **Source tracking** для производных документов — `source_content_type` + `source_object_id` через `GenericForeignKey`. Альтернатива: явный FK на родительский документ (`purchase`, `sale_order`, `production_task`). GenericFK предпочтительнее когда тип источника **может** варьироваться.

4. ✅ **Currency** для операций в иностранной валюте:
   ```python
   currency = models.ForeignKey("currency.Currency", null=True, blank=True, on_delete=models.PROTECT)
   amount_foreign = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
   exchange_rate = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
   amount_uzs = models.DecimalField(max_digits=18, decimal_places=2)  # source of truth для отчётности
   ```
   Курс снимается на `operation_date` через `apps.currency.get_rate_for(date, currency_code)`.

5. ✅ **Immutable lifecycle** для проводимых документов — наследовать `apps.common.lifecycle.ImmutableStatusMixin` и явно описать `immutable_statuses = ("posted", "cancelled")`. После проводки документ **только сторно** через `cancel`/`unpost`, не редактирование.

6. ✅ **Audit log** — viewset через `OrgScopedModelViewSet` пишет `AuditLog` автоматически на CRUD. Бизнес-сервисы (confirm/post/ship) пишут свой `audit_log()` с `action_verb`.

## Antipatterns (не делать)

- ❌ **Только `created_at` без дата-операции.** «Когда запись попала в БД» ≠ «когда операция произошла». Бухгалтер заводит вчерашнюю накладную сегодня — `created_at = сегодня`, `operation_date = вчера`.
- ❌ **Хранить `amount_foreign` без `exchange_rate`.** Тогда отчёт за прошлый год пересчитывается по сегодняшнему курсу — некорректно.
- ❌ **Ссылаться на родительский документ только через имя/код в notes.** Используйте FK или GenericFK — иначе теряется реляционная целостность и трассировка.
- ❌ **Изменять "проведённый" документ через PATCH.** Должен быть `cancel` + новый документ. Этот инвариант обеспечивает `ImmutableStatusMixin`.

## Как проверить новую модель

1. Запросите отчёт за прошлый месяц — все ваши документы попадают если их `operation_date` в периоде?
2. Найдите свой документ в `audit_log` после CRUD?
3. Нажмите `cancel` на проведённой записи — реверс делается одной операцией?
4. Откройте документ через `/traceability/?batch_id=<uuid>` — он показывается в правильном узле дерева?

Если все 4 — да, модель соответствует F0.6.
