from django.db import models

from apps.common.models import TimestampedModel, UUIDModel
from apps.common.normalize import UpperCodeMixin

from .validators import validate_inn


class Counterparty(UpperCodeMixin, UUIDModel, TimestampedModel):
    upper_code_fields = ("code",)

    class Kind(models.TextChoices):
        SUPPLIER = "supplier", "Поставщик"
        BUYER = "buyer", "Покупатель"
        OTHER = "other", "Прочее"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="counterparties",
    )
    code = models.CharField(max_length=32)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    name = models.CharField(max_length=255)
    inn = models.CharField(max_length=14, blank=True, validators=[validate_inn])
    specialization = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    balance_uzs = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    # Кредитная политика для покупателей (kind=buyer). Для других kind
    # поля игнорируются. NULL = ограничение не задано.
    credit_limit_uzs = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Максимальный совокупный долг покупателя. Если непогашенная "
            "сумма confirmed-продаж + новая продажа > лимита — confirm_sale "
            "блокируется. NULL = без ограничения."
        ),
    )
    max_overdue_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Максимальная допустимая просрочка по самому старому "
            "непогашенному счёту. Если есть счёт с просрочкой > этого "
            "значения — confirm_sale блокируется. NULL = без ограничения."
        ),
    )

    # Стартовый долг для миграции из других учётных систем. Текущий долг =
    # opening_debt_uzs + Σ(invoiced) − Σ(paid). Знак опции:
    #   • для kind=buyer (клиент): + → клиент нам должен, − → предоплата
    #   • для kind=supplier:        + → мы должны поставщику, − → переплата
    # Меняется только администратором; используется один раз при миграции.
    opening_debt_uzs = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        help_text=(
            "Стартовый долг (миграция). Положительное = долг есть, "
            "отрицательное = предоплата. По умолчанию 0."
        ),
    )
    opening_balance_date = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Дата на которую зафиксирован стартовый долг (день миграции). "
            "Используется в отчётах для фильтрации «до» / «после» миграции."
        ),
    )

    class Meta:
        ordering = ["code"]
        unique_together = (("organization", "code"),)
        indexes = [
            models.Index(fields=["organization", "kind"]),
            models.Index(fields=["name"]),
        ]
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"

    def __str__(self):
        return f"{self.code} · {self.name}"
