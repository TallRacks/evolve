from django.urls import path

from .views import dashboard_view, health, search

app_name = "core"

urlpatterns = [
    path("health/", health, name="health"),
    path("search/", search, name="search"),
    path("dashboard/", dashboard_view, name="dashboard"),
]
