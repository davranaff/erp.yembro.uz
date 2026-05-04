from rest_framework import serializers

from .models import Organization, OrganizationMembership


class OrganizationSerializer(serializers.ModelSerializer):
    accounting_currency_code = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id",
            "code",
            "name",
            "legal_name",
            "inn",
            "legal_address",
            "direction",
            "accounting_currency",
            "accounting_currency_code",
            "timezone",
            "logo",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "code",              # code — иммутабельный слуг-идентификатор
            "logo",              # загрузка логотипа — отдельным endpoint-ом (out of scope)
            "is_active",         # деактивация — только через admin
            "accounting_currency_code",
            "created_at",
            "updated_at",
        )

    def get_accounting_currency_code(self, obj):
        return obj.accounting_currency.code if obj.accounting_currency_id else None


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()
    user_full_name = serializers.SerializerMethodField()
    organization_code = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationMembership
        fields = (
            "id",
            "user",
            "organization",
            "is_active",
            "position_title",
            "work_phone",
            "work_status",
            "joined_at",
            "user_email",
            "user_full_name",
            "organization_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "joined_at",
            "user_email",
            "user_full_name",
            "organization_code",
            "created_at",
            "updated_at",
        )

    def get_user_email(self, obj):
        return obj.user.email if obj.user_id else None

    def get_user_full_name(self, obj):
        return obj.user.full_name if obj.user_id else None

    def get_organization_code(self, obj):
        return obj.organization.code if obj.organization_id else None


class OrganizationMembershipCreateSerializer(serializers.Serializer):
    """Инпут для POST /api/memberships/ — создаёт User (или переиспользует) + membership."""

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    position_title = serializers.CharField(max_length=128, required=False, allow_blank=True)
    work_phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    work_status = serializers.ChoiceField(
        choices=OrganizationMembership.WorkStatus.choices,
        default=OrganizationMembership.WorkStatus.ACTIVE,
        required=False,
    )

    def to_representation(self, instance):
        # После create возвращаем полный MembershipSerializer
        return OrganizationMembershipSerializer(instance).data
