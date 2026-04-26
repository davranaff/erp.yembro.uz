from rest_framework import serializers

from .models import Module, OrganizationModule


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = (
            "id",
            "code",
            "name",
            "kind",
            "icon",
            "sort_order",
            "is_active",
        )
        read_only_fields = fields


class OrganizationModuleSerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()
    module_name = serializers.SerializerMethodField()
    module_kind = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationModule
        fields = (
            "id",
            "organization",
            "module",
            "is_enabled",
            "enabled_at",
            "settings_json",
            "module_code",
            "module_name",
            "module_kind",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "module_code",
            "module_name",
            "module_kind",
            "created_at",
            "updated_at",
        )

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_module_name(self, obj):
        return obj.module.name if obj.module_id else None

    def get_module_kind(self, obj):
        return obj.module.kind if obj.module_id else None
