from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.common.viewsets import OrgReadOnlyViewSet, OrgScopedModelViewSet

from .models import ExpenseArticle, GLAccount, GLSubaccount, JournalEntry
from .serializers import (
    ExpenseArticleSerializer,
    GLAccountSerializer,
    GLSubaccountSerializer,
    JournalEntrySerializer,
)


class GLAccountViewSet(OrgReadOnlyViewSet):
    """/api/accounting/accounts/ — план счетов (read-only, верхний уровень)."""

    serializer_class = GLAccountSerializer
    queryset = GLAccount.objects.prefetch_related("subaccounts__module").order_by("code")
    module_code = "ledger"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["type"]
    search_fields = ["code", "name"]
    ordering = ["code"]


class GLSubaccountViewSet(OrgScopedModelViewSet):
    """
    /api/accounting/subaccounts/ — субсчета (CRUD).

    Создание/правка/удаление доступны только для уровня admin в модуле ledger.
    Удаление защищено PROTECT на JournalEntry/Payment — при попытке удалить
    используемый субсчёт вернём 409 с объяснением.
    """

    serializer_class = GLSubaccountSerializer
    queryset = GLSubaccount.objects.select_related("account", "module").order_by("code")
    module_code = "ledger"
    write_level = "admin"
    organization_field = "account__organization"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["account", "module"]
    search_fields = ["code", "name"]
    ordering = ["code"]

    def _save_kwargs_for_create(self, serializer) -> dict:
        """
        Override: у GLSubaccount нет поля organization (оно у parent account).
        Вместо этого полагаемся на валидацию в сериализаторе, которая проверяет
        что account.organization == request.organization.
        """
        return {}

    def perform_destroy(self, instance):
        """Защита от удаления субсчёта, на который есть ссылки."""
        self._write_audit(
            AuditLog.Action.DELETE,
            instance,
            verb=f"delete GLSubaccount {instance.code}",
        )
        try:
            instance.delete()
        except ProtectedError as exc:
            raise DRFValidationError(
                {"detail": (
                    f"Субсчёт {instance.code} используется в проводках/платежах "
                    f"и не может быть удалён. Сначала переназначьте ссылки."
                )}
            ) from exc


class JournalEntryViewSet(OrgReadOnlyViewSet):
    """/api/accounting/entries/ — проводки (read-only)."""

    serializer_class = JournalEntrySerializer
    queryset = JournalEntry.objects.select_related(
        "module", "debit_subaccount", "credit_subaccount",
        "currency", "counterparty", "batch", "expense_article",
    )
    module_code = "ledger"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "module",
        "debit_subaccount",
        "credit_subaccount",
        "currency",
        "counterparty",
        "batch",
        "expense_article",
    ]
    search_fields = ["doc_number", "description"]
    ordering_fields = ["entry_date", "doc_number", "amount_uzs"]
    ordering = ["-entry_date"]


class ExpenseArticleViewSet(OrgScopedModelViewSet):
    """
    /api/accounting/expense-articles/ — справочник статей расходов/доходов.

    Аналитический справочник поверх плана счетов. Использование:
        - в OPEX-модалке выбирается статья → автоматически подставляется
          default_subaccount (можно переопределить)
        - в /reports фильтрация и группировка по статьям.

    Удаление защищено PROTECT через payments/journal_entries.
    """

    serializer_class = ExpenseArticleSerializer
    queryset = ExpenseArticle.objects.select_related(
        "default_subaccount__account", "default_module", "parent",
    ).order_by("code")
    module_code = "ledger"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["kind", "is_active", "default_module", "parent"]
    search_fields = ["code", "name", "notes"]
    ordering_fields = ["code", "name", "kind"]
    ordering = ["code"]

    def perform_destroy(self, instance):
        self._write_audit(
            AuditLog.Action.DELETE,
            instance,
            verb=f"delete ExpenseArticle {instance.code}",
        )
        try:
            instance.delete()
        except ProtectedError as exc:
            raise DRFValidationError(
                {"detail": (
                    f"Статья {instance.code} используется в платежах/проводках "
                    f"и не может быть удалена. Деактивируйте её вместо удаления."
                )}
            ) from exc
