from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.decorators import action
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


# ─── Cash advances ────────────────────────────────────────────────────────


class CashAdvanceViewSet(OrgScopedModelViewSet):
    """CRUD подотчётных (выданная наличка сотрудникам).

    Lifecycle через actions:
      POST /api/accounting/cash-advances/{id}/report/   { spent_amount_uzs }
      POST /api/accounting/cash-advances/{id}/close/    { expense_article? }
      POST /api/accounting/cash-advances/{id}/cancel/   { reason? }
    """

    from .models import CashAdvance
    from .serializers import CashAdvanceSerializer

    serializer_class = CashAdvanceSerializer
    queryset = CashAdvance.objects.select_related(
        "recipient", "expense_article", "closing_journal_entry",
    )
    module_code = "ledger"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "recipient", "expense_article"]
    search_fields = ["doc_number", "purpose", "notes"]
    ordering_fields = ["issued_date", "amount_uzs", "status", "created_at"]
    ordering = ["-issued_date"]

    def perform_create(self, serializer):
        from apps.common.services.numbering import next_doc_number

        from .models import CashAdvance

        org = self.request.organization
        kwargs = self._save_kwargs_for_create(serializer)
        if not serializer.validated_data.get("doc_number"):
            kwargs["doc_number"] = next_doc_number(
                CashAdvance, organization=org, prefix="АВ",
                on_date=serializer.validated_data.get("issued_date"),
            )
        instance = serializer.save(**kwargs)
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)

    @action(detail=True, methods=["post"], url_path="report")
    def report(self, request, pk=None):
        """POST /api/accounting/cash-advances/{id}/report/

        Body: { "spent_amount_uzs": "750000" }

        Сотрудник принёс чеки. Заполняем spent + автоматически считаем
        returned (выдано − потрачено). Статус → REPORTED.
        """
        from decimal import Decimal as Dec

        from .models import CashAdvance
        from .services.cash_advances import CashAdvanceError, report_advance

        advance = self.get_object()
        spent_raw = request.data.get("spent_amount_uzs")
        if spent_raw is None:
            raise DRFValidationError({"spent_amount_uzs": "Обязательно."})
        try:
            spent = Dec(str(spent_raw))
        except (TypeError, ValueError):
            raise DRFValidationError({"spent_amount_uzs": "Неверный формат."})

        try:
            advance = report_advance(advance, spent_amount=spent, user=request.user)
        except CashAdvanceError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
            ) from exc

        from apps.audit.models import AuditLog
        self._write_audit(
            AuditLog.Action.UPDATE,
            advance,
            verb=f"advance {advance.doc_number}: reported spent={spent}",
        )
        return Response(self.get_serializer(advance).data)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        """POST /api/accounting/cash-advances/{id}/close/

        Body (опц.): { "expense_article": "uuid" }

        Создаёт JE на расходную статью, меняет статус → CLOSED.
        """
        from .models import ExpenseArticle
        from .services.cash_advances import CashAdvanceError, close_advance

        advance = self.get_object()
        article_id = request.data.get("expense_article")
        article = None
        if article_id:
            try:
                article = ExpenseArticle.objects.get(
                    id=article_id, organization=advance.organization,
                )
            except ExpenseArticle.DoesNotExist:
                raise DRFValidationError({"expense_article": "Статья не найдена."})

        try:
            advance = close_advance(advance, user=request.user, expense_article=article)
        except CashAdvanceError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
            ) from exc

        from apps.audit.models import AuditLog
        self._write_audit(
            AuditLog.Action.POST,
            advance,
            verb=f"advance {advance.doc_number} closed (JE: {advance.closing_journal_entry_id})",
        )
        return Response(self.get_serializer(advance).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """POST /api/accounting/cash-advances/{id}/cancel/  Body: { reason? }"""
        from .services.cash_advances import CashAdvanceError, cancel_advance

        advance = self.get_object()
        reason = (request.data.get("reason") or "").strip()
        try:
            advance = cancel_advance(advance, user=request.user, reason=reason)
        except CashAdvanceError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
            ) from exc

        from apps.audit.models import AuditLog
        self._write_audit(
            AuditLog.Action.UNPOST, advance,
            verb=f"advance {advance.doc_number} cancelled · {reason}",
        )
        return Response(self.get_serializer(advance).data)
