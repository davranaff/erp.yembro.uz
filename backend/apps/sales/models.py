"""
Универсальный модуль продаж (зеркало `apps/purchases`).

Один SaleOrder может продавать товары любого источника:
    - Batch (matochnik / incubation / feedlot / slaughter)
    - FeedBatch (feed)
    - VetStockBatch (vet)

В SaleItem ровно одна из трёх FK заполнена (XOR в clean()).
"""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class SaleOrder(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        CONFIRMED = "confirmed", "Проведён"
        CANCELLED = "cancelled", "Отменён"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Не оплачен"
        PARTIAL = "partial", "Частично оплачен"
        PAID = "paid", "Оплачен"
        OVERPAID = "overpaid", "Переплата"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="sale_orders",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="sale_orders",
        help_text="Source module: vet/slaughter/feedlot/...",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    date = models.DateField(db_index=True)

    customer = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.PROTECT,
        related_name="sale_orders",
    )
    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.PROTECT,
        related_name="sale_orders",
        help_text="Откуда отгружаем (склад источника).",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )

    # ─── FX-snapshot (фиксируется при confirm) ────────────────────────────
    currency = models.ForeignKey(
        "currency.Currency",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sale_orders",
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    exchange_rate_source = models.ForeignKey(
        "currency.ExchangeRate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referenced_by_sales",
    )
    exchange_rate_override = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=(
            "Ручной курс, переопределяющий CBU. Заполняется в DRAFT, "
            "применяется при confirm. Если NULL — берётся курс ЦБ."
        ),
    )
    amount_foreign = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cost_uzs = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        help_text="Сумма себестоимости (для расчёта маржи).",
    )

    # ─── Расчёты с покупателем ────────────────────────────────────────────
    paid_amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    payment_status = models.CharField(
        max_length=16,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        db_index=True,
    )
    due_date = models.DateField(
        null=True, blank=True, db_index=True,
        help_text="Плановая дата оплаты (для отчёта дебиторского старения).",
    )

    # ─── Кредит-override ─────────────────────────────────────────────────
    # Заполняется ТОЛЬКО если confirm_sale прошёл с force_credit_override=True
    # (когда у клиента превышен лимит/просрочка, но sales:admin осознанно
    # пробил продажу). Бизнес-требование: причина override обязательна —
    # для аудита и защиты от случайного «продал в долг забыл записать почему».
    credit_override_reason = models.TextField(
        blank=True,
        help_text=(
            "Причина override кредитной блокировки. Заполняется при "
            "confirm_sale(force_credit_override=True). Без причины override "
            "невозможен."
        ),
    )

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "-date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["module"]),
        ]
        verbose_name = "Продажа"
        verbose_name_plural = "Продажи"

    def __str__(self):
        return f"{self.doc_number} · {self.date}"

    def clean(self):
        super().clean()
        if (
            self.organization_id
            and self.warehouse_id
            and self.warehouse.organization_id != self.organization_id
        ):
            raise ValidationError({"warehouse": "Склад из другой организации."})
        if (
            self.organization_id
            and self.customer_id
            and self.customer.organization_id != self.organization_id
        ):
            raise ValidationError({"customer": "Покупатель из другой организации."})

    @property
    def margin_uzs(self):
        return (self.amount_uzs or 0) - (self.cost_uzs or 0)


class SaleCommunication(UUIDModel, TimestampedModel):
    """История общения с клиентом по конкретной продаже.

    Используется когда сотрудник звонит/пишет должнику и фиксирует
    ответ клиента: «обещал заплатить такого-то числа», «отказался»,
    «сменил номер», «перезвоните завтра». Это превращает продажу из
    статичного документа в живую CRM-карточку с таймлайном касаний.

    Видна на drawer-е продажи (FE), доступна для отчёта «должники без
    касаний за N дней» и подмешивается в TG-сводку для владельца.
    """

    class Method(models.TextChoices):
        CALL = "call", "Звонок"
        VISIT = "visit", "Личная встреча"
        WHATSAPP = "whatsapp", "WhatsApp"
        TELEGRAM = "telegram", "Telegram"
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        OTHER = "other", "Другое"

    class Outcome(models.TextChoices):
        PROMISED = "promised", "Обещал оплатить"
        REFUSED = "refused", "Отказался платить"
        NO_ANSWER = "no_answer", "Не ответил"
        WRONG_NUMBER = "wrong_number", "Неверный номер"
        ASKED_DEFER = "asked_defer", "Попросил отсрочку"
        OTHER = "other", "Другое"

    order = models.ForeignKey(
        SaleOrder,
        on_delete=models.CASCADE,
        related_name="communications",
    )
    contacted_at = models.DateTimeField(
        db_index=True,
        help_text="Когда сотрудник связался с клиентом.",
    )
    method = models.CharField(max_length=16, choices=Method.choices)
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    customer_response = models.TextField(
        help_text="Что ответил клиент дословно — для CRM-истории и аудита.",
    )
    promised_pay_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Что обещал САМ клиент (его слова). Используется для "
            "follow-up напоминаний если клиент не сдержал слово."
        ),
    )
    expected_pay_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Внутренний прогноз менеджера: когда оплата реально придёт. "
            "Может отличаться от promised_pay_date (например, клиент обещал "
            "пятницу, но менеджер по опыту знает что заплатит понедельник). "
            "Тоже триггерит задачу-напоминание после прохождения даты."
        ),
    )
    next_action_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Когда сотруднику перезвонить (если no_answer / отсрочка).",
    )
    internal_note = models.TextField(
        blank=True,
        help_text=(
            "Заметка менеджера для внутреннего пользования (не попадает "
            "в TG/email клиенту). Например «скандалил», «жалуется на качество», "
            "«просил скидку 5%»."
        ),
    )
    contacted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sale_communications",
        help_text="Сотрудник, выполнивший касание.",
    )

    class Meta:
        ordering = ["-contacted_at"]
        indexes = [
            models.Index(fields=["order", "-contacted_at"]),
            models.Index(fields=["promised_pay_date"]),
        ]
        verbose_name = "Касание клиента"
        verbose_name_plural = "Касания клиента"

    def __str__(self):
        return f"{self.order.doc_number} · {self.contacted_at:%Y-%m-%d} · {self.get_method_display()}"


class SaleItem(UUIDModel, TimestampedModel):
    """
    Позиция продажи. Источник указывается ровно через одну из четырёх FK
    (batch / vet_stock_batch / vet_accessory / feed_batch) — XOR в clean().

    `vet_accessory` — для аксессуаров вет-аптеки (миски, поилки и т.п.):
    нет партионного учёта, себестоимость weighted-avg, проводки через 41.01.
    """

    order = models.ForeignKey(
        SaleOrder, on_delete=models.CASCADE, related_name="items"
    )
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="sale_items",
    )

    batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )
    vet_stock_batch = models.ForeignKey(
        "vet.VetStockBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )
    vet_accessory = models.ForeignKey(
        "vet.VetAccessory",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )
    feed_batch = models.ForeignKey(
        "feed.FeedBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )
    feed_bag_lot = models.ForeignKey(
        "feed.FeedBagLot",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sale_items",
        help_text=(
            "Партия фасованного корма (мешки). При sale-confirm декрементится "
            "bags_remaining, quantity хранится в штуках мешков."
        ),
    )

    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    unit_price_uzs = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        help_text="Ручная цена продажи за единицу (UZS).",
    )

    # ─── Snapshot, заполняется при confirm ────────────────────────────────
    cost_per_unit_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    line_total_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    line_cost_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Строка продажи"
        verbose_name_plural = "Строки продажи"

    def __str__(self):
        return f"{self.nomenclature} × {self.quantity}"

    def clean(self):
        super().clean()
        sources = [
            self.batch_id, self.vet_stock_batch_id,
            self.vet_accessory_id, self.feed_batch_id, self.feed_bag_lot_id,
        ]
        non_null = [s for s in sources if s]
        if len(non_null) != 1:
            raise ValidationError(
                {
                    "__all__": (
                        "Должен быть указан ровно один источник: "
                        "batch, vet_stock_batch, vet_accessory, feed_batch "
                        "или feed_bag_lot."
                    )
                }
            )
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({"quantity": "Количество должно быть > 0."})
        if self.unit_price_uzs is not None and self.unit_price_uzs < 0:
            raise ValidationError({"unit_price_uzs": "Цена не может быть < 0."})
