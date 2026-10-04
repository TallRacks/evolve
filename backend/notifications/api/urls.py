from django.urls import path

from .views import (
    ArchiveView,
    DeliveryListView,
    DeliveryRetryView,
    ListView,
    MarkAllReadView,
    PlatformView,
    PreferenceResetView,
    PreferenceView,
    ReadView,
    UnreadCountView,
    PushSubscriptionView,
)

urlpatterns = [
    path("notifications/", ListView.as_view()),
    path("notifications/unread-count/", UnreadCountView.as_view()),
    path("notifications/push-subscription/", PushSubscriptionView.as_view()),
    path("notifications/<uuid:notification_id>/read/", ReadView.as_view()),
    path("notifications/<uuid:notification_id>/archive/", ArchiveView.as_view()),
    path("notifications/read-all/", MarkAllReadView.as_view()),
    path("notification-preferences/", PreferenceView.as_view()),
    path("notification-preferences/reset/", PreferenceResetView.as_view()),
    path("platform/notifications/", PlatformView.as_view()),
    path("platform/email-deliveries/", DeliveryListView.as_view()),
    path("platform/email-deliveries/<uuid:attempt_id>/retry/", DeliveryRetryView.as_view()),
]
