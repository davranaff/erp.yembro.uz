from django.urls import path

from .views import DashboardCashflowView, DashboardSummaryView


app_name = "dashboard"

urlpatterns = [
    path("summary/", DashboardSummaryView.as_view(), name="summary"),
    path("cashflow/", DashboardCashflowView.as_view(), name="cashflow"),
]
