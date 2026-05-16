from django.contrib import admin

from .models import ProductionBlock, StockMovement, Warehouse


@admin.register(ProductionBlock)
class ProductionBlockAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "module", "kind", "capacity", "is_active")
    list_filter = ("organization", "module", "kind", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("organization", "module", "capacity_unit")


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "module", "production_block", "is_active")
    list_filter = ("organization", "module", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = (
        "organization",
        "module",
        "production_block",
        "default_gl_subaccount",
    )


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "date",
        "organization",
        "module",
        "kind",
        "nomenclature",
        "quantity",
        "amount_uzs",
        "counterparty",
        "batch",
    )
    list_filter = ("organization", "module", "kind", "date")
    date_hierarchy = "date"
    search_fields = ("doc_number", "batch__doc_number")
    autocomplete_fields = (
        "organization",
        "module",
        "nomenclature",
        "warehouse_from",
        "warehouse_to",
        "counterparty",
        "batch",
    )

    # StockMovement, привязанный к проведённому документу (sale/purchase/
    # production_task/payment) через source_content_type — это «нога»
    # цепочки проводок. Менять количество/склад через админку без сторно
    # документа-источника = рассинхрон ГК и физики склада. Делаем такие
    # записи полностью readonly. Полностью ручные записи (source=NULL)
    # редактируются как раньше.
    def _is_linked_to_source(self, obj):
        return obj is not None and obj.source_content_type_id is not None

    def get_readonly_fields(self, request, obj=None):
        base = list(super().get_readonly_fields(request, obj))
        if self._is_linked_to_source(obj):
            return [f.name for f in self.model._meta.fields]
        return base

    def has_delete_permission(self, request, obj=None):
        if self._is_linked_to_source(obj):
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        # Прогоняем валидацию модели (kind ↔ warehouse_from/to) даже
        # при сохранении из админки — иначе можно записать OUTGOING
        # без warehouse_from.
        obj.full_clean()
        super().save_model(request, obj, form, change)
