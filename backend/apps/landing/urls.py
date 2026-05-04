from django.urls import path

from .views import DemoLeadView

app_name = "landing"

urlpatterns = [
    path("demo/", DemoLeadView.as_view(), name="demo-lead"),
]
