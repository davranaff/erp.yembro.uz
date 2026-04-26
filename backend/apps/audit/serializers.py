from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    module_code = serializers.SerializerMethodField()
    actor_email = serializers.SerializerMethodField()
    entity_type = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "module",
            "actor",
            "action",
            "action_verb",
            "entity_content_type",
            "entity_object_id",
            "entity_repr",
            "ip_address",
            "user_agent",
            "diff",
            "occurred_at",
            "module_code",
            "actor_email",
            "entity_type",
            "created_at",
        )
        read_only_fields = fields

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_actor_email(self, obj):
        return obj.actor.email if obj.actor_id else None

    def get_entity_type(self, obj):
        return obj.entity_content_type.model if obj.entity_content_type_id else None
