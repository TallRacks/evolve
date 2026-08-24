from django.urls import path

from .views import (
    DeveloperVenueListView,
    PlatformVenueDetailView,
    PlatformVenueListView,
    VenueContactDetailView,
    VenueContactsView,
    VenueDetailView,
    VenueListView,
)

urlpatterns = [
    path("venues/", VenueListView.as_view()),
    path("venues/<uuid:venue_id>/", VenueDetailView.as_view()),
    path("venues/<uuid:venue_id>/contacts/", VenueContactsView.as_view()),
    path("venues/<uuid:venue_id>/contacts/<uuid:link_id>/", VenueContactDetailView.as_view()),
    path("platform/venues/", PlatformVenueListView.as_view()),
    path("platform/venues/<uuid:venue_id>/", PlatformVenueDetailView.as_view()),
    path("developer/venues/", DeveloperVenueListView.as_view()),
]
