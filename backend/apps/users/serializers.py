from rest_framework import serializers

from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import RolePermission, UserModuleAccessOverride

from .models import User, UserFavoritePage


class MembershipOrgSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "code",
            "name",
            "direction",
            "timezone",
            "accounting_currency",
        )


class MembershipModulePermissionSerializer(serializers.Serializer):
    """
    {module_code: level} — эффективный level membership-а по каждому модулю.
    Вычисляется: max по RolePermission.level + UserModuleAccessOverride (override побеждает).
    """

    def to_representation(self, membership):
        permissions = {}

        # Базовые права через роли
        role_perms = RolePermission.objects.filter(
            role__in=membership.user_roles.values("role")
        ).values_list("module__code", "level")
        from apps.common.permissions import _LEVEL_ORDER

        for module_code, level in role_perms:
            current = permissions.get(module_code)
            if current is None or _LEVEL_ORDER.get(level, 0) > _LEVEL_ORDER.get(
                current, 0
            ):
                permissions[module_code] = level

        # Override побеждает роли
        overrides = UserModuleAccessOverride.objects.filter(
            membership=membership
        ).values_list("module__code", "level")
        for module_code, level in overrides:
            permissions[module_code] = level

        return permissions


class MembershipSerializer(serializers.ModelSerializer):
    organization = MembershipOrgSerializer(read_only=True)
    module_permissions = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationMembership
        fields = (
            "id",
            "organization",
            "position_title",
            "work_phone",
            "work_status",
            "is_active",
            "joined_at",
            "module_permissions",
        )

    def get_module_permissions(self, obj):
        return MembershipModulePermissionSerializer().to_representation(obj)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
        )
        read_only_fields = fields


class MeSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "memberships",
        )
        read_only_fields = fields

    def get_memberships(self, user):
        qs = (
            OrganizationMembership.objects.filter(user=user, is_active=True)
            .select_related("organization")
            .order_by("organization__code")
        )
        return MembershipSerializer(qs, many=True).data


class MeUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/users/me/ — разрешено редактировать только full_name и phone."""

    class Meta:
        model = User
        fields = ("full_name", "phone")

    def validate_full_name(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Не может быть пустым.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class UserFavoritePageSerializer(serializers.ModelSerializer):
    """Сериализатор закреплённой страницы (per-user)."""

    class Meta:
        model = UserFavoritePage
        fields = (
            "id",
            "href",
            "label",
            "sort_order",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_href(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Путь не может быть пустым.")
        if not value.startswith("/"):
            raise serializers.ValidationError("Путь должен начинаться со слеша.")
        return value

    def validate_label(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Название не может быть пустым.")
        return value
