from django.urls import path

from users.mobile_api import (
    MobileDeviceRevokeView,
    MobileDevicesView,
    MobileLoginView,
    MobileLogoutAllView,
    MobileLogoutView,
    MobileRefreshView,
    MobileSessionView,
)

from .views import (
    CsrfView,
    CurrentUserView,
    LoginView,
    LogoutView,
    PasswordChangeView,
    ReauthenticateView,
    SecurityActivityView,
)

app_name = "users_api"

urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("reauthenticate/", ReauthenticateView.as_view(), name="reauthenticate"),
    path("change-password/", PasswordChangeView.as_view(), name="change-password"),
    path("security-activity/", SecurityActivityView.as_view(), name="security-activity"),
]

urlpatterns += [
    path("mobile/auth/login/", MobileLoginView.as_view(), name="mobile-login"),
    path("mobile/auth/refresh/", MobileRefreshView.as_view(), name="mobile-refresh"),
    path("mobile/auth/me/", MobileSessionView.as_view(), name="mobile-me"),
    path("mobile/auth/logout/", MobileLogoutView.as_view(), name="mobile-logout"),
    path("mobile/auth/logout-all/", MobileLogoutAllView.as_view(), name="mobile-logout-all"),
    path("mobile/devices/", MobileDevicesView.as_view(), name="mobile-devices"),
    path(
        "mobile/devices/<uuid:device_id>/revoke/",
        MobileDeviceRevokeView.as_view(),
        name="mobile-device-revoke",
    ),
]
