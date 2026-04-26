from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class Payment(UUIDModel, TimestampedModel):
    """
    Универсальный платёж (AR/AP).

    direction=OUT — оплата поставщику (Dr 60 / Cr 50|51).
    direction=IN  — получение от покупателя (Dr 50|51 / Cr 62).

    channel фиксирует способ оплаты (наличные/перечисление/Click), но
    сопоставление с GL-субсчётом делает сервис Phase 8 (`post_payment`).

    FX-snapshot (currency, exchange_rate, amount_foreign, amount_uzs) —
    тот же паттерн, что в `purchases.PurchaseOrder` и
    `accounting.JournalEntry`.
    """

    class Direction(models.TextChoices):
        OUT = "out", "Оплата поставщику"
        IN = "in", "Поступление от покупателя"

    class Channel(models.TextChoices):
        CASH = "cash", "Наличные"
        TRANSFER = "transfer", "Перечисление"
        CLICK = "click", "Click"
        OTHER = "other", "Прочее"

    class Kind(models.TextChoices):
        """
        Тип платежа — определяет бизнес-сценарий. По умолчанию `counterparty`
        (оплата PO/SO, текущее поведение). Остальные — для "прочих" операций
        с произвольным contra-субсчётом.
        """
        COUNTERPARTY = "counterparty", "Оплата контрагенту/клиенту"
        OPEX = "opex", "Прочий расход"
        INCOME = "income", "Прочий доход"
        SALARY = "salary", "Зарплата"
        INTERNAL = "internal", "Внутренний перевод"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        CONFIRMED = "confirmed", "Подтверждён"
        POSTED = "posted", "Проведён"
        CANCELLED = "cancelled", "Отменён"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    module = models.ForeignKey(
        "modules.Module",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    date = models.DateField(db_index=True)

    direction = models.CharField(
        max_length=8, choices=Direction.choices, db_index=True
    )
    channel = models.CharField(
        max_length=16, choices=Channel.choices, db_index=True
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.COUNTERPARTY,
        db_index=True,
        help_text="Бизнес-тип платежа: обычная оплата контрагенту или прочая операция (зарплата, коммуналка, штраф).",
    )

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
        help_text="Обязателен для kind=counterparty. Для opex/income/salary — опционален.",
    )

    # FX snapshot (same pattern as PurchaseOrder)
    currency = models.ForeignKey(
        "currency.Currency",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    exchange_rate_source = models.ForeignKey(
        "currency.ExchangeRate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referenced_by_payments",
    )
    amount_foreign = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2)

    # GL subaccount to be used when posting (Phase 8 service fills).
    # Null in Draft; required in Phase 8 before POSTED.
    cash_subaccount = models.ForeignKey(
        "accounting.GLSubaccount",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    # Произвольный контр-субсчёт. Если задан — используется вместо
    # стандартного 60.01/62.01 (AP/AR). Применяется для kind в
    # {opex, income, salary}: Дт cash / Кт <contra> (для IN) или
    # Дт <contra> / Кт cash (для OUT).
    contra_subaccount = models.ForeignKey(
        "accounting.GLSubaccount",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="contra_payments",
        help_text="Для прочих операций: субсчёт расхода/дохода (20.XX, 26.XX, 70, 91.XX).",
    )
    expense_article = models.ForeignKey(
        "accounting.ExpenseArticle",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payments",
        help_text=(
            "Аналитическая статья (например «Газ», «Электричество»). "
            "При post_payment копируется в JournalEntry.expense_article."
        ),
    )

    # Paired journal entry (filled on POSTED by Phase 8 service)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date", "doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "-date"]),
            models.Index(fields=["organization", "direction", "status"]),
            models.Index(fields=["counterparty", "-date"]),
            models.Index(fields=["channel", "status"]),
        ]
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"

    def __str__(self):
        return f"{self.doc_number} · {self.get_direction_display()} · {self.amount_uzs}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if (
            self.counterparty_id
            and self.counterparty.organization_id != org_id
        ):
            raise ValidationError(
                {"counterparty": "Контрагент из другой организации."}
            )
        if (
            self.cash_subaccount_id
            and self.cash_subaccount.account.organization_id != org_id
        ):
            raise ValidationError(
                {"cash_subaccount": "Субсчёт из другой организации."}
            )
        if (
            self.contra_subaccount_id
            and self.contra_subaccount.account.organization_id != org_id
        ):
            raise ValidationError(
                {"contra_subaccount": "Субсчёт из другой организации."}
            )
        if (
            self.journal_entry_id
            and self.journal_entry.organization_id != org_id
        ):
            raise ValidationError(
                {"journal_entry": "Проводка из другой организации."}
            )
        if (
            self.expense_article_id
            and self.expense_article.organization_id != org_id
        ):
            raise ValidationError(
                {"expense_article": "Статья из другой организации."}
            )
        if self.amount_uzs is not None and self.amount_uzs <= 0:
            raise ValidationError({"amount_uzs": "Сумма должна быть больше нуля."})

        # counterparty обязателен только для kind=counterparty
        if self.kind == self.Kind.COUNTERPARTY and not self.counterparty_id:
            raise ValidationError(
                {"counterparty": "Для платежа контрагенту укажите Counterparty."}
            )
        # для прочих видов платежа contra_subaccount обязателен
        if (
            self.kind in {self.Kind.OPEX, self.Kind.INCOME, self.Kind.SALARY}
            and not self.contra_subaccount_id
        ):
            raise ValidationError(
                {"contra_subaccount": (
                    "Для прочих операций укажите субсчёт (статью) расхода/дохода."
                )}
            )

        # FX consistency
        has_currency = bool(self.currency_id)
        has_foreign = self.amount_foreign is not None
        has_rate = self.exchange_rate is not None
        if has_currency:
            if not (has_foreign and has_rate):
                raise ValidationError(
                    "Для валютного платежа требуются amount_foreign и exchange_rate."
                )
        else:
            if has_foreign or has_rate:
                raise ValidationError(
                    "amount_foreign и exchange_rate указываются только для валютного платежа."
                )


class PaymentAllocation(UUIDModel, TimestampedModel):
    """
    Разнесение платежа на конкретный документ (PurchaseOrder сейчас,
    SalesOrder позже). Один платёж может покрывать несколько документов;
    один документ может оплачиваться несколькими платежами.

    target — GenericFK (PurchaseOrder в Phase 7, другие позже).
    """

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="allocations"
    )
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    target_object_id = models.UUIDField()
    target = GenericForeignKey("target_content_type", "target_object_id")

    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["payment", "target_content_type", "target_object_id"]
        unique_together = (
            ("payment", "target_content_type", "target_object_id"),
        )
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"]),
            models.Index(fields=["payment"]),
        ]
        verbose_name = "Разнесение платежа"
        verbose_name_plural = "Разнесения платежей"

    def __str__(self):
        return f"{self.payment.doc_number} → {self.target} · {self.amount_uzs}"

    def clean(self):
        super().clean()
        if self.amount_uzs is not None and self.amount_uzs <= 0:
            raise ValidationError({"amount_uzs": "Сумма должна быть больше нуля."})
        # Soft-check target content_type — allow known payable/receivable documents.
        if self.target_content_type_id:
            model = self.target_content_type.model
            if model not in {"purchaseorder", "saleorder"}:
                raise ValidationError(
                    {"target_content_type": (
                        "Разнесение возможно только на закуп (PurchaseOrder) "
                        "или продажу (SaleOrder)."
                    )}
                )
