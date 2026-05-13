"""
URL conf для объединённого журнала оповещений (SMS + TG).

Вынесен в отдельный модуль чтобы config/urls.py не импортировал
notifications_views напрямую (это тянет SmsMessage до завершения
загрузки app registry — Django падает с
`RuntimeError: Model class ... doesn't declare an explicit app_label`).

См. config/urls.py — `include("apps.otp.notifications_urls")`.
"""
from django.urls import path

from .notifications_views import NotificationsListView


app_name = "notifications"

urlpatterns = [
    path("", NotificationsListView.as_view(), name="list"),
]
