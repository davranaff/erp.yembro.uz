from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CompensationPlanViewSet,
    HolidayViewSet,
    PayrollAdjustmentViewSet,
    PayrollPayoutViewSet,
    PayrollPeriodViewSet,
    PayrollRunViewSet,
    SalaryRateViewSet,
    WorkScheduleTemplateViewSet,
    WorkScheduleViewSet,
    WorkShiftViewSet,
)
from .views_employees import (
    all_balances,
    employee_accrued,
    employee_balance,
    employee_calendar,
    my_payroll,
)


router = DefaultRouter()
router.register(r"compensation-plans", CompensationPlanViewSet, basename="compensationplan")
router.register(r"rates", SalaryRateViewSet, basename="salaryrate")
router.register(r"schedule-templates", WorkScheduleTemplateViewSet, basename="scheduletemplate")
router.register(r"work-schedules", WorkScheduleViewSet, basename="workschedule")
router.register(r"work-shifts", WorkShiftViewSet, basename="workshift")
router.register(r"payouts", PayrollPayoutViewSet, basename="payrollpayout")
router.register(r"adjustments", PayrollAdjustmentViewSet, basename="payrolladjustment")
router.register(r"holidays", HolidayViewSet, basename="holiday")
router.register(r"runs", PayrollRunViewSet, basename="payrollrun")
router.register(r"periods", PayrollPeriodViewSet, basename="payrollperiod")

app_name = "payroll"

urlpatterns = router.urls + [
    path("balances/", all_balances, name="balances-all"),
    path("me/", my_payroll, name="me-payroll"),
    path("employees/<uuid:pk>/balance/", employee_balance, name="employee-balance"),
    path("employees/<uuid:pk>/accrued/", employee_accrued, name="employee-accrued"),
    path("employees/<uuid:pk>/calendar/", employee_calendar, name="employee-calendar"),
]
