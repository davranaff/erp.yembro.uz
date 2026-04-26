from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from apps.currency.serializers import ExchangeRateNestedSerializer

from .models import SaleItem, SaleOrder


class SaleItemSerializer(serializers.ModelSerializer):
    nomenclature_sku = serializers.SerializerMethodField()
    nomenclature_name = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = (
            "id",
            "nomenclature",
            "nomenclature_sku",
            "nomenclature_name",
            "batch",
            "vet_stock_batch",
            "feed_batch",
            "quantity",
            "unit_price_uzs",
            "cost_per_unit_uzs",
            "line_total_uzs",
            "line_cost_uzs",
        )
        read_only_fields = (
            "id",
            "nomenclature_sku",
            "nomenclature_name",
            "cost_per_unit_uzs",
            "line_total_uzs",
            "line_cost_uzs",
        )

    def get_nomenclature_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nomenclature_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None


class SaleOrderSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, required=False)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    currency_code = serializers.SerializerMethodField()
    module_code = serializers.SerializerMethodField()
    margin_uzs = serializers.SerializerMethodField()
    draft_total_uzs = serializers.SerializerMethodField()
    exchange_rate_source_detail = ExchangeRateNestedSerializer(
        source="exchange_rate_source", read_only=True
    )
    exchange_rate_override = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True,
    )

    doc_number = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )

    class Meta:
        model = SaleOrder
        fields = (
            "id",
            "doc_number",
            "date",
            "module",
            "module_code",
            "customer",
            "customer_name",
            "warehouse",
            "warehouse_code",
            "status",
            "payment_status",
            "paid_amount_uzs",
            "currency",
            "currency_code",
            "exchange_rate",
            "exchange_rate_source",
            "exchange_rate_source_detail",
            "exchange_rate_override",
            "amount_foreign",
            "amount_uzs",
            "cost_uzs",
            "margin_uzs",
            "draft_total_uzs",
            "notes",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "payment_status",
            "paid_amount_uzs",
            "exchange_rate",
            "exchange_rate_source",
            "exchange_rate_source_detail",
            "amount_foreign",
            "amount_uzs",
            "cost_uzs",
            "margin_uzs",
            "draft_total_uzs",
            "module_code",
            "customer_name",
            "warehouse_code",
            "currency_code",
            "created_at",
            "updated_at",
        )

    def get_currency_code(self, obj):
        return obj.currency.code if obj.currency_id else None

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_margin_uzs(self, obj):
        return str(obj.margin_uzs)

    def get_draft_total_uzs(self, obj):
        """
        Для черновиков amount_uzs/cost_uzs ещё не зафиксированы (snapshot
        берётся при confirm). Возвращаем расчётную сумму = Σ qty * unit_price
        по позициям. Для проведённых/отменённых — None (используется
        amount_uzs).
        """
        if obj.status != SaleOrder.Status.DRAFT:
            return None
        total = Decimal("0")
        # items могут быть уже prefetched / могут не быть — обращаемся через
        # related manager (1 запрос на заказ).
        for item in obj.items.all():
            qty = Decimal(item.quantity or 0)
            price = Decimal(item.unit_price_uzs or 0)
            total += qty * price
        return str(total)

    def validate(self, attrs):
        """
        Проверка остатков партий с учётом резервов в DRAFT-продажах.

        Для каждой item.batch:
            available = batch.current_quantity − Σ(qty в других DRAFT)
        Если qty (или сумма qty по batch если он указан в нескольких items)
        > available — ошибка.

        Также:
            - batch.state должен быть active
            - batch.current_module должен совпадать с order.module (физически
              в этом модуле, а не в transit/другом модуле)
        """
        from apps.batches.models import Batch

        # Валидация работает на create и update — items могут быть None
        # (без замены позиций) при PATCH без items.
        items_data = attrs.get("items")
        if items_data is None:
            return attrs

        order_module = attrs.get("module") or (
            self.instance.module if self.instance else None
        )
        instance_id = self.instance.id if self.instance else None

        # Группируем requested-qty по batch (если одна партия в нескольких строках)
        qty_by_batch: dict = defaultdict(lambda: Decimal("0"))
        for item in items_data:
            batch = item.get("batch")
            if not batch:
                continue
            qty_by_batch[batch.id] += Decimal(str(item["quantity"]))

        for batch_id, requested_qty in qty_by_batch.items():
            batch = Batch.objects.filter(pk=batch_id).select_related(
                "current_module"
            ).first()
            if batch is None:
                raise serializers.ValidationError(
                    {"items": f"Партия {batch_id} не найдена."}
                )

            if batch.state != Batch.State.ACTIVE:
                raise serializers.ValidationError(
                    {"items": (
                        f"Партия {batch.doc_number} не активна "
                        f"({batch.get_state_display()}). Продажа невозможна."
                    )}
                )

            if (
                order_module
                and batch.current_module_id
                and batch.current_module_id != order_module.id
            ):
                raise serializers.ValidationError(
                    {"items": (
                        f"Партия {batch.doc_number} физически находится "
                        f"в модуле «{batch.current_module.code}», "
                        f"продажа из «{order_module.code}» невозможна."
                    )}
                )

            # Резерв = сумма quantity в DRAFT-продажах ДРУГИХ заказов
            reserve_qs = SaleItem.objects.filter(
                batch_id=batch_id,
                order__status=SaleOrder.Status.DRAFT,
            )
            if instance_id:
                reserve_qs = reserve_qs.exclude(order_id=instance_id)
            reserved = Decimal(reserve_qs.aggregate(s=Sum("quantity"))["s"] or 0)

            available = Decimal(batch.current_quantity or 0) - reserved
            if available < 0:
                available = Decimal("0")

            if requested_qty > available:
                raise serializers.ValidationError(
                    {"items": (
                        f"Партия {batch.doc_number}: запрошено "
                        f"{requested_qty}, доступно {available} "
                        f"(остаток {batch.current_quantity}, "
                        f"зарезервировано в других черновиках {reserved})."
                    )}
                )

        # ── Валидация FeedBatch ────────────────────────────────────────
        from apps.feed.models import FeedBatch

        qty_by_feed: dict = defaultdict(lambda: Decimal("0"))
        for item in items_data:
            fb = item.get("feed_batch")
            if not fb:
                continue
            qty_by_feed[fb.id] += Decimal(str(item["quantity"]))

        for fb_id, requested_qty in qty_by_feed.items():
            fb = FeedBatch.objects.filter(pk=fb_id).first()
            if fb is None:
                raise serializers.ValidationError(
                    {"items": f"Партия комбикорма {fb_id} не найдена."}
                )

            if fb.status != FeedBatch.Status.APPROVED:
                raise serializers.ValidationError(
                    {"items": (
                        f"Партия комбикорма {fb.doc_number} в статусе "
                        f"«{fb.get_status_display()}» — продавать можно только "
                        f"одобренные. Сначала проведите контроль качества."
                    )}
                )

            # Резерв в других DRAFT
            reserve_qs = SaleItem.objects.filter(
                feed_batch_id=fb_id,
                order__status=SaleOrder.Status.DRAFT,
            )
            if instance_id:
                reserve_qs = reserve_qs.exclude(order_id=instance_id)
            reserved = Decimal(reserve_qs.aggregate(s=Sum("quantity"))["s"] or 0)

            available = Decimal(fb.current_quantity_kg or 0) - reserved
            if available < 0:
                available = Decimal("0")

            if requested_qty > available:
                raise serializers.ValidationError(
                    {"items": (
                        f"Партия комбикорма {fb.doc_number}: запрошено "
                        f"{requested_qty} кг, доступно {available} кг "
                        f"(остаток {fb.current_quantity_kg}, "
                        f"зарезервировано в черновиках {reserved})."
                    )}
                )

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = SaleOrder.objects.create(**validated_data)
        for item in items_data:
            SaleItem.objects.create(order=order, **item)
        return order

    def update(self, instance, validated_data):
        if instance.status != SaleOrder.Status.DRAFT:
            raise serializers.ValidationError(
                {"status": "Редактирование возможно только для черновика."}
            )
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                SaleItem.objects.create(order=instance, **item)
        return instance
