from django.urls import path

from .views import (
    DashboardArSummaryView,
    DashboardCashflowView,
    DashboardSummaryView,
)


app_name = "dashboard"

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="summary"),
    path("cashflow/", DashboardCashflowView.as_view(), name="cashflow"),
    path("ar-summary/", DashboardArSummaryView.as_view(), name="ar-summary"),
]
