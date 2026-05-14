# Аудит: долги клиентов в статистике

**Дата:** 2026-05-14
**Проблема (от заказчика):** «У нас есть долги у клиентов. Когда есть долги, в статистике они не должны учитываться — в статистике должны быть только актуальные (реально полученные) суммы, а не те, что висят в долгах.»

---

## TL;DR — корневая причина

Все витрины «Выручка / Продажи / Маржа» по всему приложению считаются как
**`Σ amount_uzs` проведённых заказов** — то есть по **полной сумме счёта**.
А `amount_uzs` включает в себя **непогашенный долг** (`amount_uzs − paid_amount_uzs`).

Поэтому если клиент купил на 10 млн и не заплатил ничего — в «Выручке» всё равно
показывается 10 млн. Заказчик хочет, чтобы статистика показывала **`paid_amount_uzs`**
(реально поступившие деньги), а долг шёл отдельной строкой «Дебиторка».

Модель данных для этого уже готова — у `SaleOrder` есть все нужные поля:

| Поле | Смысл |
|---|---|
| `amount_uzs` | полная сумма счёта (начислено / отгружено) |
| `paid_amount_uzs` | сколько клиент реально оплатил |
| `amount_uzs − paid_amount_uzs` | **долг** (дебиторка) — НЕ должен попадать в «выручку» |
| `payment_status` | unpaid / partial / paid / overpaid |

Чинить нужно **не данные, а формулы агрегатов** — в 6 местах (3 backend + 3 frontend).

---

## Решение, которое нужно утвердить (бизнес-вопрос)

Что должна показывать карточка **«Выручка»**? Варианты:

- **Вариант A (рекомендуемый) — разделить на две явные метрики везде:**
  - «Отгружено / Начислено» = `Σ amount_uzs` — оставить как вторичную строку (объём продаж)
  - «Оплачено / Поступило» = `Σ paid_amount_uzs` — **сделать главной цифрой**
  - Долг (`amount − paid`) уже показывается отдельной карточкой «Дебиторка» — не трогаем
- **Вариант B — просто заменить** `Σ amount_uzs` → `Σ paid_amount_uzs` везде в «выручке».
  Проще, но теряется видимость объёма отгрузок.

Дальнейшие патчи в этом документе написаны под **Вариант A**. По марже см. раздел
«Отдельный вопрос: маржа».

---

## Находки по местам

| # | Файл | Что не так | Приоритет |
|---|------|------------|-----------|
| 1 | `backend/apps/dashboard/services.py` → `kpi_summary()` | `sales_revenue_uzs` = `Σ amount_uzs` (с долгом) | **P0** |
| 2 | `frontend/src/app/(app)/dashboard/page.tsx` | KPI «Выручка» / «Прибыль» показывают п.1 | **P0** |
| 3 | `frontend/src/app/(app)/sales/page.tsx` | `revenue`/`margin` считаются клиентом из `Σ amount_uzs` | **P0** |
| 4 | `backend/apps/counterparties/views.py` → `monthly_turnover` | `sales_uzs` по месяцам = `Σ amount_uzs` (с долгом) | **P1** |
| 5 | `frontend/src/app/(app)/counterparties/[id]/page.tsx` | `totalSales` суммирует п.4 | **P1** |
| 6 | `backend/apps/holding/services.py` → `consolidate()` | `purchases_confirmed_uzs` = `Σ amount_uzs` (симметрично, сторона закупок) | **P2** |
| — | `backend/apps/dashboard/services.py` → `kpi_summary()` | `purchases_confirmed_uzs` — то же самое для закупок | **P2** |

### ✅ Что считается ПРАВИЛЬНО (не трогать)

- `payments_in_uzs` / `payments_out_uzs`, `cash_balances()`, `cashflow_chart()` —
  считаются по `Payment` со `status=POSTED`. Это и есть реальные деньги. ✓
- `debtor_balance_uzs` / `creditor_balance_uzs` на дашборде и в холдинге —
  это и **есть** долг, он так и подписан («должны нам» / «должны мы»). ✓
- `ar_summary()` и `compute_aging_report()` (`backend/apps/sales/services/aging.py`) —
  это отчёт о дебиторке, он **должен** показывать долг. ✓
- `frontend/.../sales/page.tsx` карточка «Должны нам» (`receivable`) — это долг,
  подписан корректно. ✓
- `backend/apps/warehouses/views.py` → `stats` (`Σ amount_uzs` по движениям склада) —
  это оценка склада, к долгам клиентов отношения не имеет. ✓

### ⚠️ Отдельный случай — P&L / Оборотно-сальдовая (`backend/apps/accounting/`)

`compute_pl_report`, `compute_trial_balance`, `compute_gl_ledger`
(`backend/apps/accounting/services/reports.py`) считаются по `JournalEntry`.
Проводка выручки создаётся в момент `confirm_sale` (`Дт 62.01 / Кт 90.01`) на
**полную сумму** — это **корректный бухгалтерский учёт по методу начисления**.

P&L по определению — accrual-отчёт, его **менять не нужно**. Если заказчик хочет
видеть «кассовый» P&L — это отдельная задача (добавить переключатель
«начисление / касса»), но формальный бухгалтерский P&L трогать нельзя.

---

## Детали и патчи

### 1. `backend/apps/dashboard/services.py` — `kpi_summary()` (P0)

**Сейчас** (~строки 83–92):
```python
sales_agg = (
    SaleOrder.objects.filter(
        organization=organization,
        status=SaleOrder.Status.CONFIRMED,
        date__gte=start, date__lte=end,
    ).aggregate(
        revenue=Sum("amount_uzs"),      # ❌ включает долг
        cost=Sum("cost_uzs"),
    )
)
sales_revenue = sales_agg["revenue"] or Decimal("0")
sales_cost = sales_agg["cost"] or Decimal("0")
sales_margin = sales_revenue - sales_cost   # ❌ маржа раздута долгом
```

**Стало:**
```python
sales_agg = (
    SaleOrder.objects.filter(
        organization=organization,
        status=SaleOrder.Status.CONFIRMED,
        date__gte=start, date__lte=end,
    ).aggregate(
        invoiced=Sum("amount_uzs"),       # начислено / отгружено
        paid=Sum("paid_amount_uzs"),      # ✅ реально оплачено
        cost=Sum("cost_uzs"),
    )
)
sales_invoiced = sales_agg["invoiced"] or Decimal("0")
sales_paid = sales_agg["paid"] or Decimal("0")
sales_cost = sales_agg["cost"] or Decimal("0")
sales_unpaid = sales_invoiced - sales_paid          # долг по продажам периода
sales_margin = sales_invoiced - sales_cost          # маржа по отгрузке (см. раздел «маржа»)
```

**В возвращаемом словаре** (~строки 127–143) — заменить ключ и добавить новые:
```python
    "sales_revenue_uzs": str(sales_paid),        # ✅ теперь «актуальная» сумма
    "sales_invoiced_uzs": str(sales_invoiced),   # новое: объём отгрузок (вторично)
    "sales_unpaid_uzs": str(sales_unpaid),       # новое: долг по продажам периода
    "sales_cost_uzs": str(sales_cost),
    "sales_margin_uzs": str(sales_margin),
```
> Ключ `sales_revenue_uzs` оставлен (чтобы не ломать фронт), но его значение
> теперь = оплачено. Не забыть добавить `sales_invoiced_uzs` в
> `_FINANCIAL_KPI_KEYS` в `backend/apps/dashboard/views.py` (скрытие без `ledger.r`).

**Закупки (симметрично, P2)** — `purchases_confirmed_uzs` (~строки 36–44) тоже
считается по `Σ amount_uzs`. Если нужна та же логика и для закупок — добавить
`purchases_paid_uzs = Σ paid_amount_uzs`. Заказчик жаловался только на клиентов,
поэтому это P2 — обсудить отдельно.

### 2. `frontend/src/app/(app)/dashboard/page.tsx` (P0)

KpiCard «Выручка» (~строка 146–154) сейчас:
```tsx
<KpiCard
  label="Выручка"
  sub="продажи проведённые"
  value={fmt(k.sales_revenue_uzs)}
  meta={`себест.: ${fmt(k.sales_cost_uzs)}`}
/>
```
**Стало** — главная цифра = оплачено, отгружено уходит в `meta`/`sub`:
```tsx
<KpiCard
  label="Выручка"
  sub="оплачено клиентами"
  value={fmt(k.sales_revenue_uzs)}           // теперь = оплачено
  meta={`отгружено: ${fmt(k.sales_invoiced_uzs)} · себест.: ${fmt(k.sales_cost_uzs)}`}
/>
```
- `marginPct` (~строка 106) — пересчитать от той базы, что выбрана для маржи.
- Опционально: добавить отдельную карточку «Не оплачено за период» = `k.sales_unpaid_uzs`.
- Обновить тип `DashboardKpis` в `frontend/src/types/auth.ts` (+`sales_invoiced_uzs`,
  `sales_unpaid_uzs`).

### 3. `frontend/src/app/(app)/sales/page.tsx` (P0)

**Сейчас** (строки 100–110):
```tsx
const revenue = confirmed.reduce((s, o) => s + parseFloat(o.amount_uzs || '0'), 0);   // ❌
const cost = confirmed.reduce((s, o) => s + parseFloat(o.cost_uzs || '0'), 0);
const receivable = confirmed.reduce(
  (s, o) => s + (parseFloat(o.amount_uzs || '0') - parseFloat(o.paid_amount_uzs || '0')), 0,
);
return { count, revenue, margin: revenue - cost, receivable };
```

**Стало:**
```tsx
const invoiced = confirmed.reduce((s, o) => s + parseFloat(o.amount_uzs || '0'), 0);
const revenue  = confirmed.reduce((s, o) => s + parseFloat(o.paid_amount_uzs || '0'), 0); // ✅ оплачено
const cost     = confirmed.reduce((s, o) => s + parseFloat(o.cost_uzs || '0'), 0);
const receivable = invoiced - revenue;   // долг = начислено − оплачено
return { count, invoiced, revenue, margin: revenue - cost, receivable };
```

KpiCards (~строки 148–152):
```tsx
<KpiCard label="Выручка" sub="оплачено" value={fmtUzs(String(totals.revenue))} />
<KpiCard label="Отгружено" sub="начислено" value={fmtUzs(String(totals.invoiced))} />
<KpiCard label="Маржа" sub="оплачено − себест." value={fmtUzs(String(totals.margin))} />
<KpiCard label="Должны нам" sub="не оплачено" value={fmtUzs(String(totals.receivable))} />
```

### 4. `backend/apps/counterparties/views.py` — `monthly_turnover` (P1)

В цикле помесячной агрегации (~строки 287–307) `sales_total` считается по
`Σ amount_uzs` подтверждённых продаж. Добавить `paid`:
```python
sales_agg = sale_qs.filter(
    date__gte=month_start, date__lte=month_end,
    status=SaleOrder.Status.CONFIRMED,
).aggregate(invoiced=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
sales_invoiced = sales_agg["invoiced"] or Decimal("0")
sales_paid = sales_agg["paid"] or Decimal("0")
...
months.append({
    "month": month_start.isoformat()[:7],
    "sales_uzs": str(sales_paid),            # ✅ оплачено
    "sales_invoiced_uzs": str(sales_invoiced),  # новое
    "purchases_uzs": str(purchases_total),
    "payments_in_uzs": str(payments_in),
    "payments_out_uzs": str(payments_out),
})
```

### 5. `frontend/src/app/(app)/counterparties/[id]/page.tsx` (P1)

Строка 282: `totalSales` теперь автоматически = сумма оплаченного (после п.4),
т.к. `r.sales_uzs` уже поменяет смысл. Проверить подпись метрики в UI рядом —
если написано «Продажи», уточнить на «Продажи (оплачено)». При желании показать
обе цифры — добавить `totalInvoiced` из нового `sales_invoiced_uzs`.

### 6. `backend/apps/holding/services.py` — `consolidate()` (P2)

Холдинг-консолидация в целом построена правильно: «выручку» она по факту берёт
из `payments_in_uzs` (POSTED-платежи = реальные деньги), а долг — из
`debtor_balance_uzs` (outstanding). Единственное — `purchases_confirmed_uzs`
(~строки 78–86) считается по `Σ amount_uzs` confirmed-закупок (с долгом).
Симметрично п.1 для закупок — поправить только если заказчик подтвердит, что
это тоже нужно.

---

## Отдельный вопрос: маржа

Сейчас `margin = revenue − cost`, где `revenue` раздут долгом → маржа завышена.
После фикса есть выбор базы:

- **Маржа по оплате** = `Σ paid_amount_uzs − Σ cost_uzs` — но это «кривовато»:
  себестоимость берётся целиком, а выручка частично → при частичной оплате маржа
  занижается.
- **Маржа по отгрузке (accrual)** = `Σ amount_uzs − Σ cost_uzs` — методологически
  корректная валовая маржа, но это «начисление», а не «касса».
- **Реализованная маржа (пропорционально)** = по каждому заказу
  `cost × (paid / amount)`, затем сумма. Точнее всего, но дороже по вычислениям.

**Рекомендация:** для KPI оставить **маржу по отгрузке**, но **явно подписать**
её «Маржа (по отгрузке)» / «валовая» — чтобы не путали с кассой. Цифра «Выручка»
при этом = оплачено. Это даёт честную картину: видно и сколько реально пришло
денег, и какая маржинальность бизнеса.

---

## План внедрения

1. **P0 — Дашборд + страница продаж** (пункты 1, 2, 3): backend `kpi_summary` →
   фронт `dashboard/page.tsx` и `sales/page.tsx`. Это то, на что прямо жалуется
   заказчик. Затрагивает 3 файла + типы фронта.
2. **P1 — Карточка контрагента** (пункты 4, 5): помесячный оборот клиента.
3. **P2 — Закупки** (пункт 6 + закупочная часть п.1): симметрия для стороны
   закупок — только после подтверждения заказчиком.
4. Тесты: обновить `backend/apps/dashboard/tests/test_summary.py` — добавить
   кейс «продажа с частичной оплатой → `sales_revenue_uzs` = оплаченная часть,
   `sales_invoiced_uzs` = полная сумма».

## Чек-лист правок (файлы)

- [x] `backend/apps/dashboard/services.py` — `kpi_summary()`: `paid` вместо `revenue`
- [x] `backend/apps/dashboard/views.py` — `_FINANCIAL_KPI_KEYS` += `sales_invoiced_uzs`, `sales_unpaid_uzs`
- [x] `frontend/src/app/(app)/dashboard/page.tsx` — KPI «Выручка»/«Прибыль»
- [x] `frontend/src/types/auth.ts` — тип `DashboardKpis`
- [x] `frontend/src/app/(app)/sales/page.tsx` — `totals` + KpiCards
- [x] `backend/apps/counterparties/views.py` — `monthly_turnover`
- [x] `frontend/src/hooks/useCounterparties.ts` — тип `monthly_turnover` (+`sales_invoiced_uzs`)
- [x] `frontend/src/app/(app)/counterparties/[id]/page.tsx` — `totalSales` + подписи
- [ ] `backend/apps/holding/services.py` — `purchases_confirmed_uzs` (P2 — закупки, не трогали: см. ниже)
- [x] `backend/apps/dashboard/tests/test_summary.py` — тест частичной оплаты

## Статус внедрения (2026-05-14)

**Сделано — P0 + P1.** Жалоба заказчика («долги клиентов в статистике») закрыта:
выручка на дашборде, странице продаж и в карточке контрагента теперь = реально
оплаченная часть; объём отгрузок виден отдельной строкой; долг не двоится.
Маржа — по отгрузке (валовая), явно подписана. Бэкенд-тесты `apps/dashboard` +
`apps/counterparties` зелёные, фронт `tsc --noEmit` чистый.

**Не делали — P2 (сторона закупок).** `purchases_confirmed_uzs` в дашборде и
холдинге по-прежнему = `Σ amount_uzs`. Заказчик жаловался только на долги
*клиентов*; менять семантику «закупок» без подтверждения рискованно. Правка
симметрична и займёт ~15 минут, если потребуется.
