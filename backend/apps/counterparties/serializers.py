from rest_framework import serializers

from .models import Counterparty


class CounterpartySerializer(serializers.ModelSerializer):
    class Meta:
        model = Counterparty
        fields = (
            "id",
            "code",
            "kind",
            "name",
            "inn",
            "specialization",
            "phone",
            "email",
            "address",
            "balance_uzs",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "balance_uzs", "created_at", "updated_at")
