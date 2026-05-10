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
    # HR-расширения. Заполняются только если context['include_compensation'] / ['include_balance']
    # и у юзера есть hr:r. Иначе всегда None.
    compensation_type = serializers.SerializerMethodField()
    current_rate_uzs = serializers.SerializerMethodField()       # native amount (исторически)
    current_rate_currency = serializers.SerializerMethodField()
    current_rate_uzs_equiv = serializers.SerializerMethodField() # native → UZS на сегодня
    balance_uzs = serializers.SerializerMethodField()

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
            "compensation_type",
            "current_rate_uzs",
            "current_rate_currency",
            "current_rate_uzs_equiv",
            "balance_uzs",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "joined_at",
            "user_email",
            "user_full_name",
            "organization_code",
            "compensation_type",
            "current_rate_uzs",
            "current_rate_currency",
            "current_rate_uzs_equiv",
            "balance_uzs",
            "created_at",
            "updated_at",
        )

    def get_user_email(self, obj):
        return obj.user.email if obj.user_id else None

    def get_user_full_name(self, obj):
        return obj.user.full_name if obj.user_id else None

    def get_organization_code(self, obj):
        return obj.organization.code if obj.organization_id else None

    def _hr_visible(self) -> bool:
        ctx = self.context or {}
        return bool(ctx.get("hr_visible"))

    def get_compensation_type(self, obj):
        if not self._hr_visible() or not (self.context or {}).get("include_compensation"):
            return None
        plan = getattr(obj, "compensation_plan", None)
        return plan.compensation_type if plan else None

    def get_current_rate_uzs(self, obj):
        if not self._hr_visible() or not (self.context or {}).get("include_compensation"):
            return None
        from datetime import date
        from apps.payroll.services.rates import rate_at

        rate = rate_at(obj, date.today())
        return str(rate.amount) if rate else None

    def get_current_rate_currency(self, obj):
        if not self._hr_visible() or not (self.context or {}).get("include_compensation"):
            return None
        from datetime import date
        from apps.payroll.services.rates import rate_at

        rate = rate_at(obj, date.today())
        return rate.currency.code if rate and rate.currency_id else None

    def get_current_rate_uzs_equiv(self, obj):
        """UZS-эквивалент native-ставки по курсу CBU на сегодня."""
        if not self._hr_visible() or not (self.context or {}).get("include_compensation"):
            return None
        from datetime import date
        from django.core.exceptions import ValidationError
        from apps.payroll.services.fx import convert_to_uzs
        from apps.payroll.services.rates import rate_at

        rate = rate_at(obj, date.today())
        if not rate:
            return None
        currency_code = rate.currency.code if rate.currency_id else "UZS"
        try:
            fx = convert_to_uzs(rate.amount, currency_code, date.today())
            return str(fx.amount_uzs)
        except ValidationError:
            return None

    def get_balance_uzs(self, obj):
        if not self._hr_visible() or not (self.context or {}).get("include_balance"):
            return None
        from datetime import date
        from apps.payroll.services.balance import compute_balance

        bal = compute_balance(obj, date.today())
        return str(bal.balance_uzs)


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
