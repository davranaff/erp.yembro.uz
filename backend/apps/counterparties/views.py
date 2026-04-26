from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from apps.common.viewsets import OrgScopedModelViewSet

from .models import Counterparty
from .serializers import CounterpartySerializer


class CounterpartyViewSet(OrgScopedModelViewSet):
    """
    CRUD контрагентов для текущей организации.
    Требует: IsAuthenticated + X-Organization-Code + модуль `core` (r/rw).
    """

    serializer_class = CounterpartySerializer
    queryset = Counterparty.objects.all()

    module_code = "core"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["kind", "is_active"]
    search_fields = ["code", "name", "inn"]
    ordering_fields = ["code", "name", "balance_uzs", "created_at"]
    ordering = ["code"]
