from rest_framework import serializers

from .models import Category, NomenclatureItem, Unit


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ("id", "code", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.SerializerMethodField()
    default_gl_subaccount_code = serializers.SerializerMethodField()
    default_gl_subaccount_name = serializers.SerializerMethodField()
    module_code = serializers.SerializerMethodField()
    module_name = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "parent",
            "module",
            "default_gl_subaccount",
            "parent_name",
            "module_code",
            "module_name",
            "default_gl_subaccount_code",
            "default_gl_subaccount_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "parent_name",
            "module_code",
            "module_name",
            "default_gl_subaccount_code",
            "default_gl_subaccount_name",
            "created_at",
            "updated_at",
        )

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_module_name(self, obj):
        return obj.module.name if obj.module_id else None

    def get_parent_name(self, obj):
        return obj.parent.name if obj.parent_id else None

    def get_default_gl_subaccount_code(self, obj):
        return (
            obj.default_gl_subaccount.code if obj.default_gl_subaccount_id else None
        )

    def get_default_gl_subaccount_name(self, obj):
        return (
            obj.default_gl_subaccount.name if obj.default_gl_subaccount_id else None
        )


class NomenclatureItemSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    module_code = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()
    default_gl_subaccount_code = serializers.SerializerMethodField()
    default_gl_subaccount_name = serializers.SerializerMethodField()

    class Meta:
        model = NomenclatureItem
        fields = (
            "id",
            "sku",
            "name",
            "category",
            "unit",
            "default_gl_subaccount",
            "barcode",
            "is_active",
            "notes",
            "base_moisture_pct",
            "category_name",
            "module_code",
            "unit_code",
            "default_gl_subaccount_code",
            "default_gl_subaccount_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "category_name",
            "module_code",
            "unit_code",
            "default_gl_subaccount_code",
            "default_gl_subaccount_name",
            "created_at",
            "updated_at",
        )

    def get_module_code(self, obj):
        if not obj.category_id or not obj.category.module_id:
            return None
        return obj.category.module.code

    def get_category_name(self, obj):
        return obj.category.name if obj.category_id else None

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit_id else None

    def get_default_gl_subaccount_code(self, obj):
        return (
            obj.default_gl_subaccount.code if obj.default_gl_subaccount_id else None
        )

    def get_default_gl_subaccount_name(self, obj):
        return (
            obj.default_gl_subaccount.name if obj.default_gl_subaccount_id else None
        )

    def validate(self, attrs):
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        if org is None:
            return attrs
        category = attrs.get("category") or getattr(self.instance, "category", None)
        unit = attrs.get("unit") or getattr(self.instance, "unit", None)
        if category and category.organization_id != org.id:
            raise serializers.ValidationError(
                {"category": "Категория из другой организации."}
            )
        if unit and unit.organization_id != org.id:
            raise serializers.ValidationError(
                {"unit": "Единица из другой организации."}
            )
        sub = attrs.get("default_gl_subaccount") or getattr(
            self.instance, "default_gl_subaccount", None
        )
        if sub and sub.account.organization_id != org.id:
            raise serializers.ValidationError(
                {"default_gl_subaccount": "Субсчёт из другой организации."}
            )
        return attrs
