from django.urls import path

from .views import (
    SendDebtReminderView,
    TelegramWebhookView,
    TgCounterpartyLinkView,
    TgLinkTokenView,
    TgMyLinkView,
)

urlpatterns = [
    path("webhook/", TelegramWebhookView.as_view(), name="tg-webhook"),
    path("link-token/", TgLinkTokenView.as_view(), name="tg-link-token"),
    path("links/me/", TgMyLinkView.as_view(), name="tg-link-me"),
    path("links/counterparty/<uuid:pk>/", TgCounterpartyLinkView.as_view(), name="tg-link-counterparty"),
    path("send-debt-reminder/", SendDebtReminderView.as_view(), name="tg-send-debt-reminder"),
]
