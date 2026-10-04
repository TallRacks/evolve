from django.urls import path

from .views import (
    CalendarView,
    CalendarExportView,
    DeveloperCalendarView,
    EventDetailView,
    EventListView,
    EventStatusView,
    PlatformCalendarView,
    PortalCalendarView,
)

urlpatterns = [
    path("calendar/", CalendarView.as_view()),
    path("calendar/export.ics", CalendarExportView.as_view()),
    path("calendar/events/", EventListView.as_view()),
    path("calendar/events/<uuid:event_id>/", EventDetailView.as_view()),
    path("calendar/events/<uuid:event_id>/status/", EventStatusView.as_view()),
    path("artist-portal/calendar/", PortalCalendarView.as_view()),
    path("platform/calendar/", PlatformCalendarView.as_view()),
    path("developer/calendar/", DeveloperCalendarView.as_view()),
]
