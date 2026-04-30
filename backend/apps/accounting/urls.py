from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CashAdvanceViewSet,
    ExpenseArticleViewSet,
    GLAccountViewSet,
    GLSubaccountViewSet,
    JournalEntryViewSet,
)
from .views_reports import GlLedgerView, PlReportView, TrialBalanceView


router = DefaultRouter()
router.register(r"accounts", GLAccountViewSet, basename="glaccount")
router.register(r"subaccounts", GLSubaccountViewSet, basename="glsubaccount")
router.register(r"entries", JournalEntryViewSet, basename="journalentry")
router.register(r"expense-articles", ExpenseArticleViewSet, basename="expensearticle")
router.register(r"cash-advances", CashAdvanceViewSet, basename="cashadvance")

app_name = "accounting"

urlpatterns = router.urls + [
    path("reports/trial-balance/", TrialBalanceView.as_view(), name="report-trial-balance"),
    path("reports/gl-ledger/", GlLedgerView.as_view(), name="report-gl-ledger"),
    path("reports/pl/", PlReportView.as_view(), name="report-pl"),
]
