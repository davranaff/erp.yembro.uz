from django.urls import path

from .views import OtpRequestView, OtpVerifyView


app_name = "otp"

urlpatterns = [
    path("request/", OtpRequestView.as_view(), name="request"),
    path("verify/", OtpVerifyView.as_view(), name="verify"),
]
