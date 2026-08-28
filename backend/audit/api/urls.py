from django.urls import path

from .views import PlatformAuditView, WorkspaceActivityView

urlpatterns = [
    path("activity/", WorkspaceActivityView.as_view(), name="workspace-activity"),
    path("platform/audit/", PlatformAuditView.as_view(), name="platform-audit"),
]
