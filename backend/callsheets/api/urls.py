from django.urls import path

from callsheets.models import (
    CallSheetAccommodationItem,
    CallSheetContactEntry,
    CallSheetScheduleItem,
    CallSheetTeamEntry,
    CallSheetTravelItem,
)

from .serializers import (
    AccommodationSerializer,
    ContactSerializer,
    ScheduleSerializer,
    TeamSerializer,
    TravelSerializer,
)
from .views import (
    BookingCallSheetView,
    CallSheetDetailView,
    ChildDetailView,
    ChildListView,
    DeveloperCallSheetListView,
    LifecycleView,
    PlatformCallSheetDetailView,
    PlatformCallSheetListView,
    VersionDetailView,
    VersionListView,
)

urlpatterns = [
    path("bookings/<uuid:booking_id>/call-sheet/", BookingCallSheetView.as_view()),
    path("call-sheets/<uuid:call_sheet_id>/", CallSheetDetailView.as_view()),
    path("call-sheets/<uuid:call_sheet_id>/versions/", VersionListView.as_view()),
    path("call-sheet-versions/<uuid:version_id>/", VersionDetailView.as_view()),
    path("call-sheet-versions/<uuid:version_id>/ready/", LifecycleView.as_view(operation="ready")),
    path(
        "call-sheet-versions/<uuid:version_id>/publish/", LifecycleView.as_view(operation="publish")
    ),
    path(
        "call-sheet-versions/<uuid:version_id>/cancel/", LifecycleView.as_view(operation="cancel")
    ),
    path(
        "call-sheet-versions/<uuid:version_id>/refresh-from-booking/",
        LifecycleView.as_view(operation="refresh"),
    ),
    path("platform/call-sheets/", PlatformCallSheetListView.as_view()),
    path("platform/call-sheets/<uuid:call_sheet_id>/", PlatformCallSheetDetailView.as_view()),
    path("developer/call-sheets/", DeveloperCallSheetListView.as_view()),
]

children = (
    (
        "schedule",
        CallSheetScheduleItem,
        ScheduleSerializer,
        "schedule_items",
        "callsheet.schedule_updated",
        "callsheet.schedule_removed",
        "callsheet.schedule_added",
    ),
    (
        "team",
        CallSheetTeamEntry,
        TeamSerializer,
        "team_entries",
        "callsheet.team_updated",
        "callsheet.team_updated",
    ),
    (
        "contacts",
        CallSheetContactEntry,
        ContactSerializer,
        "contact_entries",
        "callsheet.contacts_updated",
        "callsheet.contacts_updated",
    ),
    (
        "travel",
        CallSheetTravelItem,
        TravelSerializer,
        "travel_items",
        "callsheet.travel_updated",
        "callsheet.travel_updated",
    ),
    (
        "accommodation",
        CallSheetAccommodationItem,
        AccommodationSerializer,
        "accommodation_items",
        "callsheet.accommodation_updated",
        "callsheet.accommodation_updated",
    ),
)
for segment, model, serializer, relation, action, remove_action, *create_actions in children:
    create_action = create_actions[0] if create_actions else action
    urlpatterns += [
        path(
            f"call-sheet-versions/<uuid:version_id>/{segment}/",
            ChildListView.as_view(
                model=model,
                serializer_class=serializer,
                relation=relation,
                audit_action=action,
                create_action=create_action,
            ),
        ),
        path(
            f"call-sheet-versions/<uuid:version_id>/{segment}/<uuid:child_id>/",
            ChildDetailView.as_view(
                model=model,
                serializer_class=serializer,
                audit_action=action,
                remove_action=remove_action,
            ),
        ),
    ]
