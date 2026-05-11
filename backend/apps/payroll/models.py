from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class PayrollAccrualSnapshot(UUIDModel, TimestampedModel):
    """
    Денормализованный кэш балансов сотрудников. Обновляется celery beat'ом
    раз в сутки (или on-demand). Используется отчётом /payroll/balances/
    при больших объёмах данных (1000+ сотрудников).

    Если snapshot.computed_at > N часов назад — fallback к live-расчёту
    через compute_balance.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="accrual_snapshots",
    )
    employee = models.OneToOneField(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="accrual_snapshot",
    )
    as_of = models.DateField(db_index=True)
    accrued_total = models.DecimalField(max_digits=18, decimal_places=2)
    paid_total = models.DecimalField(max_digits=18, decimal_places=2)
    adjustments_plus = models.DecimalField(max_digits=18, decimal_places=2)
    adjustments_minus = models.DecimalField(max_digits=18, decimal_places=2)
    balance_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    computed_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "computed_at"]),
            models.Index(fields=["organization", "balance_uzs"]),
        ]
        verbose_name = "Снимок баланса ЗП"
        verbose_name_plural = "Снимки балансов ЗП"

    def __str__(self):
        return f"{self.employee} · {self.balance_uzs} (as of {self.as_of})"


class Holiday(UUIDModel, TimestampedModel):
    """
    Календарный праздник. organization=NULL — государственный праздник UZ,
    общий для всех. organization=<X> — корпоративный (например внутренний выходной).

    В expected_workdays_in_month праздничные дни вычитаются из рабочих,
    чтобы pro-rated MONTHLY_SALARY считался корректно.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        null=True, blank=True,
        on_delete=models.PROTECT,
        related_name="holidays",
        help_text="NULL = государственный (общий). Иначе — корпоративный.",
    )
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=128)
    is_paid = models.BooleanField(
        default=True,
        help_text="Оплачивается ли этот день при окладе (True для гос. праздников).",
    )

    class Meta:
        ordering = ["date"]
        unique_together = (("organization", "date"),)
        indexes = [models.Index(fields=["date"])]
        verbose_name = "Праздник"
        verbose_name_plural = "Праздники"

    def __str__(self):
        return f"{self.date} · {self.name}"


class CompensationPlan(UUIDModel, TimestampedModel):
    """
    План оплаты сотрудника. OneToOne с OrganizationMembership — расширение
    HR-данных без модификации core-таблицы. Текущая ставка живёт в SalaryRate.
    """

    class Type(models.TextChoices):
        MONTHLY_SALARY = "monthly_salary", "Оклад в месяц"
        PER_SHIFT = "per_shift", "Ставка за смену"
        PER_HOUR = "per_hour", "Ставка за час"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="compensation_plans",
    )
    employee = models.OneToOneField(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="compensation_plan",
    )
    compensation_type = models.CharField(
        max_length=24, choices=Type.choices, db_index=True,
        default=Type.MONTHLY_SALARY,
    )
    currency = models.ForeignKey(
        "currency.Currency", on_delete=models.PROTECT, related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "compensation_type"])]
        verbose_name = "План оплаты"
        verbose_name_plural = "Планы оплаты"

    def __str__(self):
        return f"{self.employee} · {self.get_compensation_type_display()}"

    def clean(self):
        super().clean()
        if (
            self.employee_id
            and self.organization_id
            and self.employee.organization_id != self.organization_id
        ):
            raise ValidationError({"employee": "Сотрудник из другой организации."})


class CompensationPlanHistory(UUIDModel, TimestampedModel):
    """
    История изменений compensation_type сотрудника. Создаётся автоматически
    при первом создании CompensationPlan и при последующих изменениях.

    accrue_for_period использует тип, активный на shift_date (важно для
    смешанных периодов — например per_shift до 1 июня, monthly_salary после).

    Если истории нет (для новых записей до P2.2) — fallback к текущему
    CompensationPlan.compensation_type.
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="compensation_history",
    )
    employee = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="compensation_history",
    )
    compensation_type = models.CharField(
        max_length=24, choices=CompensationPlan.Type.choices,
    )
    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True, db_index=True)
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        ordering = ["-effective_from"]
        indexes = [
            models.Index(fields=["employee", "-effective_from"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="payroll_comphistory_valid_interval",
            ),
        ]
        verbose_name = "История типа оплаты"
        verbose_name_plural = "История типа оплаты"

    def __str__(self):
        return f"{self.employee} · {self.compensation_type} с {self.effective_from}"


class SalaryRate(UUIDModel, TimestampedModel):
    """
    Историческая ставка сотрудника. Open-ended интервалы (effective_to=NULL — текущая).
    При установке новой ставки сервис rates.set_rate закрывает прошлую.

    Семантика amount по compensation_type:
        - MONTHLY_SALARY → сумма в месяц
        - PER_SHIFT → сумма за смену
        - PER_HOUR → сумма за час
    """

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="salary_rates",
    )
    employee = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="salary_rates",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.ForeignKey(
        "currency.Currency", on_delete=models.PROTECT, related_name="+",
    )
    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True, db_index=True)
    reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        ordering = ["-effective_from"]
        indexes = [
            models.Index(fields=["employee", "-effective_from"]),
            models.Index(fields=["organization", "effective_from", "effective_to"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="payroll_rate_valid_interval",
            ),
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="payroll_rate_amount_positive",
            ),
        ]
        verbose_name = "Ставка ЗП"
        verbose_name_plural = "Ставки ЗП"

    def __str__(self):
        return f"{self.employee} · {self.amount} с {self.effective_from}"

    def clean(self):
        super().clean()
        if (
            self.employee_id
            and self.organization_id
            and self.employee.organization_id != self.organization_id
        ):
            raise ValidationError({"employee": "Сотрудник из другой организации."})


class WorkScheduleTemplate(UUIDModel, TimestampedModel):
    """
    Шаблон рабочего графика. Pattern в JSONB интерпретируется services.schedule.

    WEEKDAY_MASK pattern:
        {"weekdays": [0,1,2,3,4], "start": "09:00", "end": "18:00", "duration_hours": 8}
        weekdays — Monday=0..Sunday=6.

    ROTATION pattern:
        {"work_days": 2, "rest_days": 2, "anchor_date": "2026-01-01",
         "start": "08:00", "end": "20:00", "duration_hours": 12}
    """

    class PatternKind(models.TextChoices):
        WEEKDAY_MASK = "weekday_mask", "По дням недели"
        ROTATION = "rotation", "Сменный график"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="schedule_templates",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    pattern_kind = models.CharField(
        max_length=24, choices=PatternKind.choices, db_index=True,
    )
    pattern = models.JSONField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = (("organization", "code"),)
        indexes = [models.Index(fields=["organization", "is_active"])]
        verbose_name = "Шаблон графика"
        verbose_name_plural = "Шаблоны графиков"

    def __str__(self):
        return f"{self.code} · {self.name}"

    def clean(self):
        super().clean()
        from apps.payroll.services.schedule import validate_pattern
        validate_pattern(self.pattern_kind, self.pattern)


class WorkSchedule(UUIDModel, TimestampedModel):
    """Назначение шаблона графика на сотрудника с интервалом действия."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="work_schedules",
    )
    employee = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="work_schedules",
    )
    template = models.ForeignKey(
        WorkScheduleTemplate,
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-effective_from"]
        indexes = [models.Index(fields=["employee", "-effective_from"])]
        constraints = [
            models.CheckConstraint(
                check=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="payroll_workschedule_valid_interval",
            ),
        ]
        verbose_name = "Назначение графика"
        verbose_name_plural = "Назначения графиков"

    def __str__(self):
        return f"{self.employee} · {self.template.code}"

    def clean(self):
        super().clean()
        if (
            self.employee_id
            and self.organization_id
            and self.employee.organization_id != self.organization_id
        ):
            raise ValidationError({"employee": "Сотрудник из другой организации."})
        if (
            self.template_id
            and self.organization_id
            and self.template.organization_id != self.organization_id
        ):
            raise ValidationError({"template": "Шаблон из другой организации."})


class WorkShift(UUIDModel, TimestampedModel):
    """
    Фактическая смена / запись табеля. Один статус на дату на сотрудника
    (multi-shift в день — Phase 2 через shift_index).

    Source отслеживает происхождение записи:
        - TEMPLATE — сгенерирована из шаблона apply_template_to_period
        - MANUAL — заведена вручную (override)
        - IMPORT — импорт из внешней системы
    """

    class Kind(models.TextChoices):
        WORK = "work", "Рабочая смена"
        OVERTIME = "overtime", "Сверхурочная"
        VACATION = "vacation", "Отпуск"
        SICK_LEAVE = "sick_leave", "Больничный"
        ABSENCE = "absence", "Прогул"
        DAY_OFF = "day_off", "Выходной"
        HOLIDAY = "holiday", "Праздник"

    class Source(models.TextChoices):
        TEMPLATE = "template", "Из шаблона"
        MANUAL = "manual", "Ручная"
        IMPORT = "import", "Импорт"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="work_shifts",
    )
    employee = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.CASCADE,
        related_name="work_shifts",
    )
    shift_date = models.DateField(db_index=True)
    shift_index = models.PositiveSmallIntegerField(
        default=0,
        help_text="0 — основная смена дня; 1 — ночная или дополнительная.",
    )
    kind = models.CharField(
        max_length=16, choices=Kind.choices,
        default=Kind.WORK, db_index=True,
    )
    source = models.CharField(
        max_length=16, choices=Source.choices,
        default=Source.MANUAL, db_index=True,
    )
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
    )
    source_template = models.ForeignKey(
        WorkScheduleTemplate, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_shifts",
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        ordering = ["-shift_date", "shift_index"]
        unique_together = (("employee", "shift_date", "shift_index"),)
        indexes = [
            models.Index(fields=["organization", "-shift_date"]),
            models.Index(fields=["employee", "-shift_date"]),
            models.Index(fields=["organization", "kind", "shift_date"]),
        ]
        verbose_name = "Смена"
        verbose_name_plural = "Смены"

    def __str__(self):
        suffix = f" #{self.shift_index}" if self.shift_index else ""
        return f"{self.employee} · {self.shift_date}{suffix} · {self.get_kind_display()}"

    def clean(self):
        super().clean()
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({"end_at": "Конец смены раньше начала."})
        if self.hours is not None and self.hours <= 0:
            raise ValidationError({"hours": "Часы должны быть > 0."})
        if (
            self.employee_id
            and self.organization_id
            and self.employee.organization_id != self.organization_id
        ):
            raise ValidationError({"employee": "Сотрудник из другой организации."})
        # Запрет редактирования смен в закрытом периоде.
        if self.shift_date and self.organization_id:
            from .services.period import assert_date_open
            assert_date_open(self.organization, self.shift_date, field_label="shift_date")


class PayrollPayout(UUIDModel, TimestampedModel):
    """
    Связка между Payment (kind=salary, OUT) и сотрудником/периодом.
    Payment остаётся универсальным; HR-метаданные живут здесь.
    """

    class Type(models.TextChoices):
        ADVANCE = "advance", "Аванс"
        SALARY = "salary", "ЗП"
        BONUS = "bonus", "Премия"
        CORRECTION = "correction", "Корректировка/доплата"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_payouts",
    )
    employee = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="payroll_payouts",
    )
    type = models.CharField(
        max_length=16, choices=Type.choices,
        default=Type.SALARY, db_index=True,
    )
    period_from = models.DateField()
    period_to = models.DateField()
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="payroll_payout",
        help_text="Реальный кассовый платёж OUT, kind=salary.",
    )
    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    notes = models.TextField(blank=True)
    run = models.ForeignKey(
        "payroll.PayrollRun",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="payouts",
        help_text="Запуск ведомости, в рамках которого создан этот payout.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        ordering = ["-period_to", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "-period_to"]),
            models.Index(fields=["employee", "-period_to"]),
            models.Index(fields=["employee", "type"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_uzs__gt=0),
                name="payroll_payout_amount_positive",
            ),
            models.CheckConstraint(
                check=models.Q(period_to__gte=models.F("period_from")),
                name="payroll_payout_valid_period",
            ),
        ]
        verbose_name = "Выплата ЗП"
        verbose_name_plural = "Выплаты ЗП"

    def __str__(self):
        return f"{self.employee} · {self.get_type_display()} · {self.amount_uzs}"

    def clean(self):
        super().clean()
        if self.payment_id and self.payment.organization_id != self.organization_id:
            raise ValidationError({"payment": "Платёж из другой организации."})
        if self.payment_id:
            from apps.payments.models import Payment as _P
            if self.payment.kind != _P.Kind.SALARY:
                raise ValidationError({"payment": "Платёж должен быть kind=salary."})
            if self.payment.direction != _P.Direction.OUT:
                raise ValidationError({"payment": "Платёж должен быть direction=OUT."})
        if (
            self.employee_id
            and self.organization_id
            and self.employee.organization_id != self.organization_id
        ):
            raise ValidationError({"employee": "Сотрудник из другой организации."})


class PayrollRun(UUIDModel, TimestampedModel):
    """
    Запуск массовой ведомости на выплату.

    Lifecycle:
        draft (preview) → executed (posted)
            нет: cancelled через массовый cancel-payouts.

    Хранит метаданные и связку на созданные PayrollPayout. Не CRUD —
    создаётся через специальный endpoint /api/payroll/runs/execute/,
    который атомарно создаёт N выплат.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        EXECUTED = "executed", "Выполнено"
        CANCELLED = "cancelled", "Отменено"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_runs",
    )
    period_from = models.DateField()
    period_to = models.DateField()
    payout_type = models.CharField(
        max_length=16,
        choices=PayrollPayout.Type.choices,
        default=PayrollPayout.Type.SALARY,
        help_text="Тип создаваемых PayrollPayout (advance/salary/bonus).",
    )
    cash_subaccount = models.ForeignKey(
        "accounting.GLSubaccount",
        on_delete=models.PROTECT,
        related_name="+",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices,
        default=Status.DRAFT, db_index=True,
    )
    employees_count = models.PositiveIntegerField(default=0)
    total_amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period_to", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "-period_to"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Ведомость на выплату"
        verbose_name_plural = "Ведомости на выплату"

    def __str__(self):
        return f"Run {self.period_from}..{self.period_to} · {self.total_amount_uzs}"


class PayrollPeriod(UUIDModel, TimestampedModel):
    """
    Закрытый учётный период ЗП. После закрытия запрещено редактировать
    WorkShift, PayrollAdjustment и SalaryRate с датами внутри периода.
    Только org-admin может переоткрыть.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Открыт"
        CLOSED = "closed", "Закрыт"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_periods",
    )
    period_from = models.DateField()
    period_to = models.DateField()
    status = models.CharField(
        max_length=8, choices=Status.choices,
        default=Status.OPEN, db_index=True,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_to"]
        indexes = [
            models.Index(fields=["organization", "-period_to"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(period_to__gte=models.F("period_from")),
                name="payroll_period_valid_range",
            ),
        ]
        verbose_name = "Закрытый период ЗП"
        verbose_name_plural = "Закрытые периоды ЗП"

    def __str__(self):
        return f"{self.period_from}..{self.period_to} [{self.status}]"


class PayrollAdjustment(UUIDModel, TimestampedModel):
    """
    Начисление/удержание без cash-движения. Влияет на accrued_total в balance.

    Семантика kind:
        BONUS, CORRECTION_PLUS → +accrued (увеличивает долг компании)
        DEDUCTION, CORRECTION_MINUS → −accrued (уменьшает долг)

    `effective_date` — дата отнесения корректировки (фильтр по периоду).
    """

    class Kind(models.TextChoices):
        BONUS = "bonus", "Премия"
        DEDUCTION = "deduction", "Удержание"
        CORRECTION_PLUS = "correction_plus", "Доначисление"
        CORRECTION_MINUS = "correction_minus", "Сторно начисления"

    POSITIVE_KINDS = ("bonus", "correction_plus")
    NEGATIVE_KINDS = ("deduction", "correction_minus")

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="payroll_adjustments",
    )
    employee = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="payroll_adjustments",
    )
    kind = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    effective_date = models.DateField(db_index=True)
    amount_uzs = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        ordering = ["-effective_date"]
        indexes = [
            models.Index(fields=["organization", "-effective_date"]),
            models.Index(fields=["employee", "-effective_date"]),
            models.Index(fields=["employee", "kind"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount_uzs__gt=0),
                name="payroll_adj_amount_positive",
            ),
        ]
        verbose_name = "Корректировка ЗП"
        verbose_name_plural = "Корректировки ЗП"

    def __str__(self):
        return f"{self.employee} · {self.get_kind_display()} · {self.amount_uzs}"

    def clean(self):
        super().clean()
        if (
            self.employee_id
            and self.organization_id
            and self.employee.organization_id != self.organization_id
        ):
            raise ValidationError({"employee": "Сотрудник из другой организации."})
        # Запрет создания/изменения корректировок в закрытом периоде.
        if self.effective_date and self.organization_id:
            from .services.period import assert_date_open
            assert_date_open(self.organization, self.effective_date, field_label="effective_date")

    @property
    def signed_amount(self) -> "Decimal":
        from decimal import Decimal as _D
        if self.kind in self.POSITIVE_KINDS:
            return self.amount_uzs
        return -_D(self.amount_uzs)
