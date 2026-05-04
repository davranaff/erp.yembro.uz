from django.urls import path

from .views import HoldingCompaniesView


app_name = "holding"

urlpatterns = [
    path("companies/", HoldingCompaniesView.as_view(), name="companies"),
]
