import django_filters

from .models import ExchangeRate


class ExchangeRateFilter(django_filters.FilterSet):
    currency = django_filters.CharFilter(field_name="currency__code", lookup_expr="iexact")
    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = ExchangeRate
        fields = ("currency", "date", "source")
