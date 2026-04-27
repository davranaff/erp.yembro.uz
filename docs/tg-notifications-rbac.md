# TG уведомления — RBAC фильтрация

**Дата:** 2026-04-27

## Проблема

При подключении Telegram к ERP любой пользователь (даже с ролью «смотритель» / только чтение) получал все уведомления наравне с администратором, а также мог выполнять все команды бота (`/report`, `/stock`, `/cashflow`, `/production`), получая полные финансовые данные без проверки прав.

## Что изменено

### `backend/apps/tgbot/tasks.py` — `notify_admins_task`

Добавлен опциональный параметр `module_code`. Если передан — получатели фильтруются через RBAC: уведомление доходит только пользователям с уровнем доступа `>= r` к указанному модулю.

```python
notify_admins_task(text, organization_id, module_code="purchases")
```

### `backend/apps/purchases/views.py` и `backend/apps/payments/views.py`

Вызовы `notify_admins_task` обновлены: теперь передают `module_code="purchases"`, так что уведомления о закупках и платежах получают только пользователи с доступом к модулю `purchases`.

### `backend/apps/tgbot/commands.py`

Добавлена функция `_has_module_access(link, module_code)` — проверяет RBAC через `OrganizationMembership` и `_effective_level`.

Каждая команда теперь требует конкретный доступ:

| Команда | Требуемый модуль |
|---------|-----------------|
| `/report` | `reports` |
| `/stock` | `ledger` |
| `/cashflow` | `reports` |
| `/production` | `feedlot` |

При недостаточных правах бот отвечает: `⛔ Нет доступа к модулю <название>.`

## Затронутые файлы

- `backend/apps/tgbot/tasks.py`
- `backend/apps/tgbot/commands.py`
- `backend/apps/purchases/views.py`
- `backend/apps/payments/views.py`
