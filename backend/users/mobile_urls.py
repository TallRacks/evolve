from django.urls import path

from .mobile_api import (
    MobileDeviceRevokeView,
    MobileDevicesView,
    MobileLoginView,
    MobileLogoutAllView,
    MobileLogoutView,
    MobileRefreshView,
    MobileSessionView,
)

app_name = "mobile_api"

urlpatterns = [
    path("auth/login/", MobileLoginView.as_view(), name="login"),
    path("auth/refresh/", MobileRefreshView.as_view(), name="refresh"),
    path("auth/me/", MobileSessionView.as_view(), name="me"),
    path("auth/logout/", MobileLogoutView.as_view(), name="logout"),
    path("auth/logout-all/", MobileLogoutAllView.as_view(), name="logout-all"),
    path("devices/", MobileDevicesView.as_view(), name="devices"),
    path(
        "devices/<uuid:device_id>/revoke/", MobileDeviceRevokeView.as_view(), name="device-revoke"
    ),
]
