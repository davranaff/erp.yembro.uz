from rest_framework import serializers

from .models import DemoLead


class DemoLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoLead
        fields = ["name", "contact", "company"]
