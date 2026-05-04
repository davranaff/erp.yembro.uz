from rest_framework import serializers

from .models import Role, RolePermission, UserModuleAccessOverride, UserRole


class RolePermissionSerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()
    module_name = serializers.SerializerMethodField()

    class Meta:
        model = RolePermission
        fields = (
            "id",
            "role",
            "module",
            "level",
            "module_code",
            "module_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "module_code",
            "module_name",
            "created_at",
            "updated_at",
        )

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_module_name(self, obj):
        return obj.module.name if obj.module_id else None


class RoleSerializer(serializers.ModelSerializer):
    permissions = RolePermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = (
            "id",
            "code",
            "name",
            "description",
            "is_system",
            "is_active",
            "permissions",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "is_system",
            "permissions",
            "created_at",
            "updated_at",
        )


class UserRoleSerializer(serializers.ModelSerializer):
    role_code = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserRole
        fields = (
            "id",
            "membership",
            "role",
            "assigned_by",
            "assigned_at",
            "role_code",
            "role_name",
            "user_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "assigned_at",
            "role_code",
            "role_name",
            "user_email",
            "created_at",
            "updated_at",
        )

    def get_role_code(self, obj):
        return obj.role.code if obj.role_id else None

    def get_role_name(self, obj):
        return obj.role.name if obj.role_id else None

    def get_user_email(self, obj):
        if not obj.membership_id:
            return None
        return obj.membership.user.email if obj.membership.user_id else None


class UserModuleAccessOverrideSerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = UserModuleAccessOverride
        fields = (
            "id",
            "membership",
            "module",
            "level",
            "reason",
            "module_code",
            "user_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "module_code",
            "user_email",
            "created_at",
            "updated_at",
        )

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_user_email(self, obj):
        if not obj.membership_id:
            return None
        return obj.membership.user.email if obj.membership.user_id else None
