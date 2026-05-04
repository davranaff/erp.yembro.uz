# ТЗ Yembro ERP v1 — Implementation Spec

**Статус:** draft, принимаются правки владельцем до старта Этапа 0.
**Scope:** операционная система птицефабрики (производство, склад, касса, долги, KPI). **Без бухгалтерии** — см. §13.

---

## 1. Стратегия

ERP = операционная система птицефабрики, не бухгалтерия. Бухгалтер работает параллельно в 1С/Excel, сверяется с ERP раз в месяц по кассе и складу. Решение письменно фиксируется с владельцем до старта разработки.

## 2. Биологический порядок модулей

```
Маточник → Инкубация → Фабрика → Убойня → Разделка/Продажа
     ↑         ↑          ↑         ↑
     └─ Корм ──┴──────────┘         │
                ↑                   │
                └── Вет аптека ─────┘
```

Порядок **внедрения** не совпадает с биологическим — см. §6.

## 3. Параллельные треки (с первого дня)

### Трек A — Operator UX / Mobile / Offline

- **Mobile-first PWA.** Responsive-формы для daily-logs, перевесов, отгрузок, инвентаризаций. Крупные кнопки, числовой ввод, быстрые +1/-1 для падежа, QR-скан для идентификации партий.
- **Поэтапный offline** (решение по вопросу #5):
  - Этап 0: PWA manifest + service worker + кэш статики. Online-only. Mobile-адаптация существующих форм.
  - Этап 1: offline queue + conflict resolution только на critical-формах (daily-log, перевес, инвентаризация). IndexedDB для локального буфера.
  - Этап 6+ (позже): offline на все сущности.
- **Telegram-бот** как альтернативный канал ввода простых метрик.
- **Валидация на вводе**: падёж ≤ численности, расход корма ≤ остатка, закрытие дня блокирует незаполненный вчерашний log.
- **Критерий приёмки Этапа 1:** заполнение daily-log ≤2 мин у реального оператора.

### Трек B — Финансовая архитектура (без бухучёта)

Структура транзакций правильная с первого дня — чтобы в будущем можно было выгрузить/построить бух-модуль без переписывания. См. F0.6.

## 4. Этап 0 — Фундамент (оценка: 5–7 рабочих дней)

> Оценка повышена с 3–4 дней — в исходной оценке не учитывались hierarchical categories + transfers + advances, это ощутимые миграции.

### F0.1 Аудит и seed справочников — 0.5 дня
- Проверить отсутствие дублирования `poultry_types` / `measurement_units` / `warehouses` между модулями. Всё строго через `core.*`.
- Дополнить фикстуры: базовые породы (broiler-308, broiler-ross, layer-hylin, layer-lohmann), части разделки, типы кормов, ингредиенты.

### F0.2 Аудит склада — 0.5 дня
- Каждая цепочка пишет `stock_movements`: приход кормов → incoming, расход на фабрику → outgoing, полуфабрикат → incoming, отгрузка → outgoing, лекарства → incoming/outgoing, яйца → incoming/outgoing, птенцы → incoming/outgoing, мясо → incoming/outgoing.
- Закрыть дыры (если найдутся). Добавить интеграционные тесты на end-to-end движения.

### F0.3 Финансы auto-AR/AP — 0.25 дня
- Подтвердить работу markers-based sync. Категории покрывают реальные операции. Патч по необходимости.

### F0.4 Inter-department transfers — 1 день

**Решение (по вопросу #1): вариант C — расширить существующие shipments**, а не строить обобщённый слой. Меньше миграций, понятнее пользователю.

На все existing shipment-сущности (`chick_shipments`, `factory_shipments`, `feed_product_shipments`, `egg_shipments`, `slaughter_semi_product_shipments`) добавить:
- `destination_department_id` UUID nullable — если NULL, отгрузка внешняя (клиенту)
- `acknowledged_at` timestamp nullable
- `acknowledged_by` FK employee nullable
- `received_quantity` numeric nullable (для фиксации факта приёмки с возможным расхождением)
- `status` enum: `sent` / `received` / `discrepancy` (заменяет текущий неявный статус)

Auto-сопоставление: когда отгрузка с `destination_department_id` создана, принимающий отдел видит её в inbox → жмёт "принять" → фиксируется `acknowledged_at/by/received_quantity`, `status` пересчитывается.

Миграция: у существующих строк `status = 'received'`, `acknowledged_at = shipped_on + 1 day`, `acknowledged_by = created_by`.

### F0.5 Scope-аудит по department — 0.5 дня
- В `BaseService.list/get/update/delete` поставить фильтр по `department_id` актора через user-scope. Проверить что НЕ обходится через direct repo calls.
- Написать тест: пользователь отдела А не может прочитать/изменить сущность отдела Б, даже если у роли есть `{prefix}.read`.

### F0.6 Структура транзакций — 0.75 дня

На `cash_transactions` и `stock_movements` обязательны:
- `operation_date` (дата операции, не `created_at`)
- `department_id`
- `category_id` FK на иерархический справочник (для cash_transactions)
- `counterparty_type` enum (`client` / `supplier` / `employee` / null) + `counterparty_id` nullable
- `source_type` varchar + `source_id` UUID (polymorphic link на родителя: 'slaughter_shipment', 'factory_shipment', 'manual', 'advance_reconciliation', ...)
- `status` enum: `draft` / `posted`. Posted редактируется только через сторно (см. F0.8).
- `currency_id` FK + `amount` numeric + `exchange_rate_to_base` numeric + `amount_in_base` numeric (generated column: `amount * exchange_rate_to_base`)
- `created_by`, `created_at`, `updated_at`

Индексы: `(department_id, operation_date)`, `(category_id, operation_date)`, `(source_type, source_id)`, `(counterparty_type, counterparty_id)`.

### F0.7 Иерархические категории — 1 день

**Решение (по вопросу #3):** категории → tree с `parent_id`. Leaf-only для транзакций.

Миграция:
1. `expense_categories` → `operation_categories` (переименование, т.к. теперь покрывают и доходы через `flow_type` enum: `income` / `expense`).
2. Добавить `parent_id` FK self, `is_leaf` boolean computed.
3. Seed дерева из фикстуры (см. §Приложение A).
4. Существующие категории мигрируются как leaf под новый root "Legacy — требует reassign" — задача владельца разметить их до старта Этапа 1. Я выдам draft-маппинг.
5. Новые транзакции блокируются на не-leaf через constraint `CHECK (is_leaf = true)` на FK.
6. Старые транзакции остаются as-is (не мигрируем категории постфактум — владелец разметит вручную через bulk-UI).

### F0.8 Долги — immutable posted + reversal — 1 день

**Решение (по вопросу #2):**
- Debt имеет `status = draft | posted | reversed`.
- Пока отгрузка `draft` → debt `draft`, апсертится как сейчас.
- Отгрузка переходит в `posted` → debt становится `posted`, immutable.
- Редактирование `posted` отгрузки → UI требует "сторно и новая отгрузка"; в БД: старая отгрузка остаётся, создаётся reversal entry (отрицательная) + новая корректная.
- Миграция: все текущие debts → `status = 'posted'`.

### F0.9 Аудит RBAC — 0.25 дня
- Тесты: пересечение permission + scope. Permission есть, scope нет → 403. Permission нет → 403. Оба есть → 200.

### F0.10 Advances (подотчётные) — 1 день

**Решение (по вопросу #4): вариант B — через cash_transactions + source_type/source_id-цепочку.**

- Выдача под отчёт: `cash_transaction(kind='expense', category='advance_to_employee', counterparty=employee, source_type='advance')`.
- Внутренняя сущность `employee_advances` отслеживает состояние (остаток, срок возврата), но деньгами двигает только через `cash_transactions`.
- Списание по чеку: `cash_transaction(kind='expense', category='…', source_type='advance_reconciliation', source_id=advance.id)`.
- Возврат остатка: `cash_transaction(kind='income', category='advance_return', source_type='advance', source_id=advance.id)`.
- Баланс advance = сумма выданных − сумма списаний − сумма возвратов. Алерт на просроченные.

### F0.11 Зарплата как касса — 0.25 дня

- Категория `payroll` под root `Персонал`.
- `cash_transaction(kind='expense', category='payroll/role', counterparty=employee, source_type='payroll_payout')`.
- Отдельной сущности "ведомость" нет — это не для ГНК, это фиксация выдачи налички.

### F0.12 Owner sign-off — 0.25 дня

Подготовить 1-страничный документ (RU+UZ) для владельца: что в scope, что вне scope (§13), пилотная ферма, роли. Владелец подписывает до старта Этапа 1.

**Результат Этапа 0:** ~20 точечных миграций, обновлённые модели, фикстуры категорий, PWA-skeleton, тесты scope/RBAC.

## 5. Этап 1 — Фабрика end-to-end (оценка: 5–7 дней)

- **F1.1** `flocks.needs_daily_log` computed; Telegram-пуш в 10:00 (таскик-джоба) если за вчерашний день не заполнено.
- **F1.2** Flock KPI на UI партии: FCR, mortality %, cost per bird (выручка пока без — на UAT).
- **F1.3** Mobile-форма daily-log оптимизирована: 6 полей, autofocus, числовая клавиатура, +1/-1 для mortality, QR-скан партии.
- **F1.4** Валидации на вводе: `mortality ≤ current_count`, `feed_consumed_kg ≤ warehouse_stock`, блок закрытия дня при незаполненном вчера.
- **F1.5** Offline queue для daily-log формы (первая сущность с полным offline).

## 6. Порядок внедрения

```
Этап 0 (фундамент)
  ↓
Этап 1 (Фабрика) ──→ UAT 2–4 недели ──→ критерии пройдены?
  ↓                                     │ нет
Этап 2 (Корма)                          ↓
  ↓                               дорабатываем Mobile/UX
Этап 3 (Вет аптека)
  ↓
Этап 4 (Убойня)
  ↓
Этап 5 (Маточник + Инкубация)
  ↓
Этап 6 (Дашборды + KPI-алерты)
```

## 7. UAT — пилотная ферма

**Критерии выхода (все 4 обязательны):**
- ≥80% daily-logs заполнены до 12:00 (измеримо: `SELECT COUNT(*) FROM flocks WHERE last_log_date < CURRENT_DATE AND CURRENT_TIME > '12:00'`)
- <5% записей требуют ручной коррекции в первые 24 часа после ввода
- Среднее время заполнения формы ≤2 мин (логируем на клиенте, отправляем в analytics endpoint)
- Zero критических багов (P0/P1) в течение последних 7 дней UAT

Не пройдены → не стартуем Этап 2. Доработка Mobile-трека до повторного UAT.

**Prerequisite:** владелец определяет пилотную ферму за 2 недели до старта Этапа 1 (договорённость, доступ, устройства).

## 8. Этап 2 — Корма (оценка: 5–6 дней)

- **FD2.1** `feed_types.base_humidity_pct`, `feed_types.shrinkage_rate_per_month`. Аналогично `feed_ingredients`.
- **FD2.2** Сущность `feed_stock_reweigh(warehouse_id, feed_type_id, reweigh_date, book_quantity, actual_quantity, delta, reason)`.
  - Настраиваемый период per-warehouse / per-feed-type через поле `reweigh_schedule_days`.
  - Обязателен при полной инвентаризации склада.
  - Обязателен при отгрузке крупной партии (>настраиваемый threshold kg).
- **FD2.3** Алерт в Telegram владельцу при `|delta| > norm_shrinkage_for_period`.

## 9. Этап 3 — Вет аптека (оценка: 3–4 дня)

- **M3.1** FEFO: при создании `medicine_consumption` UI предлагает партию с ближайшим `expiry_date` (уже `WHERE quantity_remaining > 0 ORDER BY expiry_date ASC LIMIT 1`).
- **M3.2** Таскик-джоба: раз в день генерирует Telegram-алерты на партии с `expiry_date − today ∈ {30, 14, 7}`.
- **M3.3** `medicine_batches.cost_price`, `medicine_batches.sale_price`. При consumption с `factory_flock_id` → списание на cost. При отгрузке внешнему client → по sale.

## 10. Этап 4 — Убойня (оценка: 4–5 дней)

- **S4.1** `poultry_type_yield_standards(poultry_type_id, meat_pct, waste_pct, avg_weight_kg, tolerance_pct)`.
- **S4.2** `slaughter_part_types(code, name, poultry_type_id, yield_pct_of_carcass, tolerance_pct)` — голень/крыло/филе/тушка, нормативы per-порода.
- **S4.3** На processing read-schema вычисляем:
  - `actual_meat_pct = (first_sort_weight + second_sort_weight) / arrival_weight × 100`
  - `actual_waste_pct = bad_weight / arrival_weight × 100`
  - `meat_variance_pct = actual_meat_pct − standard.meat_pct`
  - Алерт:
    - `meat_variance_pct < −tolerance_pct` → Telegram CRITICAL (потери)
    - `meat_variance_pct > +tolerance_pct` → Telegram WARN (ошибка взвешивания или подозрительно хорошо)
- **S4.4** Блокировка отгрузки при failed QC (уже в обзоре).

## 11. Этап 5 — Маточник + Инкубация (оценка: 4–5 дней)

- **E5.1** На `egg_production` два баланса:
  - Производственный: `total_produced = healthy + broken + defective` → CHECK constraint
  - Логистический: `healthy = to_incubation + to_sale + to_internal_use + in_stock` → service-level validation (in_stock вычисляется по остатку из stock_movements)
- **E5.2** Новая сущность `layer_flocks` (партия несушки, отдельно от бройлеров). FK `egg_production.layer_flock_id`. KPI несушек: яиц/день/голова.
- **I5.3** `incubation_batches.hatch_rate_pct = incubation_runs.chicks_hatched / incubation_batches.eggs_loaded × 100`. KPI в UI партии.

## 12. Этап 6 — Дашборды и KPI-алерты (оценка: 3–4 дня)

- План/факт по ключевым KPI (FCR, hatch rate, meat %, усушка корма).
- **Главный отчёт: Cash Flow** — приход/расход по дереву категорий, drill-down, недельная/месячная разбивка, фильтр по отделу.
- Overview всей организации (мультиферма).
- Per-department view.

## 13. Операционные правила

- **Склад и касса живут в разных измерениях.** Связь только через приход (AP) и отгрузку (AR).
- **Audit logs** обязательны — уже реализовано через BaseService.
- **Telegram-алерты** по HR-привязке:
  - Незаполненный daily-log
  - Усушка сверх норматива
  - Истечение лекарств
  - Failed QC
  - Критическое отклонение meat %
- **Статус транзакций:** draft → posted, posted редактируется через сторно.
- Закрытие периода в бухгалтерском смысле **не делаем**.

## 14. Что ВНЕ scope

- ❌ План счетов, двойная запись
- ❌ НДС-учёт, книга покупок/продаж
- ❌ ЭСФ, интеграция с soliq.uz
- ❌ Официальные зарплатные ведомости, отчётность в ГНК
- ❌ Амортизация основных средств
- ❌ Закрытие периода в бухгалтерском смысле
- ❌ P&L, баланс в бухгалтерской форме
- ❌ Интеграция с 1С / внешними системами на первом этапе

Структура `cash_transactions` (F0.6) позволит выгрузить данные или построить бух-модуль позже без переписывания.

## 15. Немедленные действия

1. ✅ **Закоммитить текущую работу** (slaughter split + dashboard analytics) — готово, тесты зелёные.
2. ⏳ **Sign-off владельца** на §1 и §14 (заготовка документа — F0.12).
3. ⏳ **Определить пилотную ферму** (не позже 2 недель до Этапа 1).
4. ⏳ **Старт Этапа 0** сразу после §15.1. Mobile-трек начинается с PWA-skeleton в первый день Этапа 0.

---

## Приложение A — Seed дерева категорий операций

```
Производство
├── Фабрика
│   ├── Корма (расход)
│   ├── Лекарства
│   ├── Электричество
│   ├── Вода
│   ├── Ремонт оборудования
│   └── Прочие производственные
├── Маточник
│   ├── Корма несушки
│   ├── Лекарства
│   └── Прочие
├── Инкубация
│   ├── Электричество
│   └── Расходники
├── Убойня
│   ├── Упаковка
│   ├── Электричество
│   └── Санитария
├── Цех кормов
│   ├── Сырьё (приход)
│   └── Электричество
└── Вет аптека
    └── Закупка лекарств

Персонал
├── Зарплата АУП
├── Зарплата производство
├── Премии
├── Подотчётные — выдача
├── Подотчётные — возврат
└── Компенсации

Административные
├── Аренда
├── Связь и интернет
├── Транспорт
├── Топливо
├── Офисные расходы
└── Юридические

Продажи (доходы)
├── Продажа мяса
├── Продажа полуфабрикатов
├── Продажа яиц
├── Продажа птенцов
├── Продажа кормов сторонним
└── Продажа лекарств сторонним

Прочие
├── Штрафы
├── Возвраты
└── Нераспределённые
```

---

## Приложение B — Открытые вопросы (ждём ответа владельца)

1. Какая ферма пилотная?
2. Кто ответственный за daily-log с каждой стороны (оператор + супервайзер)?
3. Устройства операторов — свои телефоны или нужно закупать?
4. Telegram-рабочие группы для алертов — существуют или создаём?
5. Языки интерфейса для операторов — только uz, или uz + ru?
