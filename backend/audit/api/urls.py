from django.urls import path

from .views import PlatformAuditView

urlpatterns = [path("platform/audit/", PlatformAuditView.as_view(), name="platform-audit")]
