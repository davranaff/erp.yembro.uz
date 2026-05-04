from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class GLAccount(UUIDModel, TimestampedModel):
    class Type(models.TextChoices):
        ASSET = "asset", "Актив"
        LIABILITY = "liability", "Пассив"
        EQUITY = "equity", "Капитал"
        INCOME = "income", "Доход"
        EXPENSE = "expense", "Затраты"
        SERVICE = "service", "Служебный"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="gl_accounts",
    )
    code = models.CharField(max_length=8)
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=16, choices=Type.choices)

    class Meta:
        ordering = ["code"]
        unique_together = (("organization", "code"),)
        verbose_name = "Счёт ГК"
        verbose_name_plural = "План счетов"

    def __str__(self):
        return f"{self.code} · {self.name}"


class GLSubaccount(UUIDModel, TimestampedModel):
    """
    Организация унаследуется через `account.organization` —
    прямого FK нет, чтобы не денормализовать.
    """

    account = models.ForeignKey(
        GLAccount, on_delete=models.PROTECT, related_name="subaccounts"
    )
    module = models.ForeignKey(
        "modules.Module",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="gl_subaccounts",
    )
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=128)

    class Meta:
        unique_together = ("account", "code")
        ordering = ["code"]
        indexes = [models.Index(fields=["code"])]
        verbose_name = "Субсчёт"
        verbose_name_plural = "Субсчета"

    def __str__(self):
        return f"{self.code} · {self.name}"


class ExpenseArticle(UUIDModel, TimestampedModel):
    """
    Статья расходов/доходов — аналитическое измерение поверх плана счетов.

    Зачем: технолог думает в категориях бизнеса («газ», «зарплата», «вакцины»),
    бухгалтер — в счетах ГК (26.01, 70, 10.03). Статья — мост между ними.
    Один и тот же субсчёт 26.01 «Аренда и коммуналка» может быть детализирован
    в статьях «Газ», «Электричество», «Вода», «Отопление». Отчёты в разрезе
    статей дают бизнес-аналитику без раздувания плана счетов.

    Поля:
        - code/name — короткий код и наименование
        - default_subaccount — FK на субсчёт ГК; при выборе статьи в OPEX
          модалке этот субсчёт автоматически подставляется в Дт (для расхода)
          или Кт (для дохода).
        - default_module — модуль по умолчанию (опц., для подсказок)
        - kind — тип операции (expense/income/salary/transfer); фильтрует
          выпадающий список в UI по направлению платежа
        - parent — иерархия (Коммуналка → Газ, Электричество, Вода)
        - is_active — мягкое архивирование
    """

    class Kind(models.TextChoices):
        EXPENSE = "expense", "Расход"
        INCOME = "income", "Доход"
        SALARY = "salary", "Зарплата"
        TRANSFER = "transfer", "Перевод/прочее"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="expense_articles",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    kind = models.CharField(
        max_length=16, choices=Kind.choices, default=Kind.EXPENSE, db_index=True
    )

    default_subaccount = models.ForeignKey(
        GLSubaccount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="default_for_articles",
        help_text=(
            "Субсчёт ГК по умолчанию. При выборе этой статьи в OPEX-модалке "
            "субсчёт подставится автоматически."
        ),
    )
    default_module = models.ForeignKey(
        "modules.Module",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="default_for_articles",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("organization", "code"),)
        indexes = [
            models.Index(fields=["organization", "kind", "is_active"]),
        ]
        verbose_name = "Статья расходов/доходов"
        verbose_name_plural = "Статьи расходов/доходов"

    def __str__(self):
        return f"{self.code} · {self.name}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if (
            self.default_subaccount_id
            and self.default_subaccount.account.organization_id != org_id
        ):
            raise ValidationError(
                {"default_subaccount": "Субсчёт из другой организации."}
            )
        if self.parent_id and self.parent.organization_id != org_id:
            raise ValidationError({"parent": "Родительская статья из другой организации."})
        if self.parent_id == self.id and self.id is not None:
            raise ValidationError({"parent": "Статья не может быть родителем сама себе."})


class JournalEntry(UUIDModel, TimestampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    module = models.ForeignKey(
        "modules.Module",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    entry_date = models.DateField(db_index=True)
    description = models.CharField(max_length=500)

    debit_subaccount = models.ForeignKey(
        GLSubaccount,
        on_delete=models.PROTECT,
        related_name="debit_entries",
    )
    credit_subaccount = models.ForeignKey(
        GLSubaccount,
        on_delete=models.PROTECT,
        related_name="credit_entries",
    )

    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2)

    currency = models.ForeignKey(
        "currency.Currency",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    amount_foreign = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )

    source_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    source_object_id = models.UUIDField(null=True, blank=True)
    source = GenericForeignKey("source_content_type", "source_object_id")

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_entries",
    )
    expense_article = models.ForeignKey(
        ExpenseArticle,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="journal_entries",
        help_text=(
            "Аналитическая статья расходов/доходов поверх плана счетов. "
            "Заполняется автоматически из Payment.expense_article при post_payment."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "-entry_date"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["source_content_type", "source_object_id"]),
        ]
        verbose_name = "Проводка"
        verbose_name_plural = "Проводки"

    def __str__(self):
        return f"{self.doc_number} · {self.entry_date}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if self.debit_subaccount_id:
            if self.debit_subaccount.account.organization_id != org_id:
                raise ValidationError(
                    {"debit_subaccount": "Счёт дебета из другой организации."}
                )
        if self.credit_subaccount_id:
            if self.credit_subaccount.account.organization_id != org_id:
                raise ValidationError(
                    {"credit_subaccount": "Счёт кредита из другой организации."}
                )
        if self.counterparty_id and self.counterparty.organization_id != org_id:
            raise ValidationError(
                {"counterparty": "Контрагент из другой организации."}
            )
        if self.batch_id and self.batch.organization_id != org_id:
            raise ValidationError({"batch": "Партия из другой организации."})
        if (
            self.expense_article_id
            and self.expense_article.organization_id != org_id
        ):
            raise ValidationError(
                {"expense_article": "Статья из другой организации."}
            )


# ─── Cash advances (подотчётные) ──────────────────────────────────────────


class CashAdvance(UUIDModel, TimestampedModel):
    """Подотчётные деньги, выданные сотруднику.

    Lifecycle:
      ISSUED → REPORTED → CLOSED
        │         │          │
        │         │          └─ остаток возвращён в кассу + создана JE
        │         └─ сотрудник отчитался (заполнен spent_amount_uzs + чеки)
        └─ выдали наличку из кассы (создаётся Payment OUT)

    Не наследует ImmutableStatusMixin: бизнес-логика статусов сложнее
    (можно отчитаться повторно если ошиблись с суммой). Жёстко защищаем
    только переход CLOSED → * (через clean+ViewSet action).
    """

    class Status(models.TextChoices):
        ISSUED = "issued", "Выдано"
        REPORTED = "reported", "Отчитался"
        CLOSED = "closed", "Закрыто"
        CANCELLED = "cancelled", "Отменено"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="cash_advances",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    issued_date = models.DateField(db_index=True)
    closed_date = models.DateField(null=True, blank=True)

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cash_advances",
        help_text="Сотрудник, которому выдан подотчёт.",
    )
    purpose = models.CharField(
        max_length=300,
        help_text="На что выдан подотчёт (например «закупка ГСМ для трактора»).",
    )

    amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2,
        help_text="Сколько выдали наличными.",
    )
    spent_amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        help_text="По чекам / отчёту — сколько потрачено.",
    )
    returned_amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        help_text="Сколько вернули в кассу остатком (= amount − spent).",
    )

    expense_article = models.ForeignKey(
        ExpenseArticle,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="cash_advances",
        help_text=(
            "Статья расходов, на которую списываются потраченные средства "
            "при закрытии. Если не указана — закрытие требует ручной правки JE."
        ),
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ISSUED,
        db_index=True,
    )
    issued_payment = models.OneToOneField(
        "payments.Payment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="advance_issued_for",
        help_text="Платёж OUT, который выдал наличные сотруднику.",
    )
    closing_journal_entry = models.OneToOneField(
        JournalEntry,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="closes_advance",
        help_text="Проводка списания на расходную статью при закрытии.",
    )

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cash_advances_created",
    )

    class Meta:
        ordering = ["-issued_date", "-doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["organization", "-issued_date"]),
        ]
        verbose_name = "Подотчёт (выданная наличка)"
        verbose_name_plural = "Подотчёты"

    def __str__(self) -> str:
        return f"{self.doc_number} · {self.recipient} · {self.amount_uzs} сум"

    def clean(self):
        super().clean()
        if self.amount_uzs is not None and self.amount_uzs <= 0:
            raise ValidationError({"amount_uzs": "Сумма должна быть больше нуля."})
        if self.spent_amount_uzs is not None and self.amount_uzs is not None:
            if self.spent_amount_uzs > self.amount_uzs:
                raise ValidationError(
                    {"spent_amount_uzs": "Потрачено больше чем выдано."}
                )
        if self.returned_amount_uzs is not None and self.amount_uzs is not None:
            if self.returned_amount_uzs > self.amount_uzs:
                raise ValidationError(
                    {"returned_amount_uzs": "Возврат больше чем выдано."}
                )
