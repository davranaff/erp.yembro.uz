from __future__ import annotations

from rest_framework import serializers

from .models import TgLink, TgLinkToken


class TgLinkSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True, default=None)
    counterparty_name = serializers.CharField(
        source="counterparty.name", read_only=True, default=None
    )

    class Meta:
        model = TgLink
        fields = (
            "id", "chat_id", "tg_username", "is_active",
            "user", "user_email",
            "counterparty", "counterparty_name",
            "created_at",
        )
        read_only_fields = (
            "id", "chat_id", "tg_username", "user", "user_email",
            "counterparty", "counterparty_name", "created_at",
        )


class TgLinkTokenSerializer(serializers.ModelSerializer):
    bot_url = serializers.SerializerMethodField()

    class Meta:
        model = TgLinkToken
        fields = ("id", "token", "expires_at", "used", "bot_url")
        read_only_fields = ("id", "token", "expires_at", "used", "bot_url")

    def get_bot_url(self, obj) -> str:
        from django.conf import settings
        bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "")
        if bot_username:
            return f"https://t.me/{bot_username}?start={obj.token}"
        return f"https://t.me/?start={obj.token}"


class TgLinkTokenCreateSerializer(serializers.Serializer):
    counterparty = serializers.UUIDField(required=False, allow_null=True)
