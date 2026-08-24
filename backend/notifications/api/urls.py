from django.urls import path

from .views import (
    ArchiveView,
    ListView,
    MarkAllReadView,
    PlatformView,
    PreferenceView,
    ReadView,
    UnreadCountView,
)

urlpatterns = [
    path("notifications/", ListView.as_view()),
    path("notifications/unread-count/", UnreadCountView.as_view()),
    path("notifications/<uuid:notification_id>/read/", ReadView.as_view()),
    path("notifications/<uuid:notification_id>/archive/", ArchiveView.as_view()),
    path("notifications/read-all/", MarkAllReadView.as_view()),
    path("notification-preferences/", PreferenceView.as_view()),
    path("platform/notifications/", PlatformView.as_view()),
]
