from django.urls import path

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
