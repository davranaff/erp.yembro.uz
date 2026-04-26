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
