from django.urls import path

from .sms_views import (
    SmsBalanceView,
    SmsCallbackView,
    SmsListView,
    SmsSendView,
)


app_name = "sms"

urlpatterns = [
    path("send/", SmsSendView.as_view(), name="send"),
    path("messages/", SmsListView.as_view(), name="messages"),
    path("balance/", SmsBalanceView.as_view(), name="balance"),
    path("callback/<str:secret>/", SmsCallbackView.as_view(), name="callback"),
]
