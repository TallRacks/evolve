from django.urls import path

from .views import (
    BookingContactDetailView,
    BookingContactsView,
    BookingDetailView,
    BookingListView,
    BookingStatusHistoryView,
    BookingStatusView,
    BookingTeamDetailView,
    BookingTeamView,
    DeveloperBookingListView,
    PlatformBookingDetailView,
    PlatformBookingListView,
)

urlpatterns = [
    path("bookings/", BookingListView.as_view(), name="booking-list"),
    path("bookings/<uuid:booking_id>/", BookingDetailView.as_view(), name="booking-detail"),
    path("bookings/<uuid:booking_id>/status/", BookingStatusView.as_view(), name="booking-status"),
    path(
        "bookings/<uuid:booking_id>/status-history/",
        BookingStatusHistoryView.as_view(),
        name="booking-status-history",
    ),
    path("bookings/<uuid:booking_id>/team/", BookingTeamView.as_view(), name="booking-team"),
    path(
        "bookings/<uuid:booking_id>/team/<uuid:assignment_id>/",
        BookingTeamDetailView.as_view(),
        name="booking-team-detail",
    ),
    path(
        "bookings/<uuid:booking_id>/contacts/",
        BookingContactsView.as_view(),
        name="booking-contacts",
    ),
    path(
        "bookings/<uuid:booking_id>/contacts/<uuid:assignment_id>/",
        BookingContactDetailView.as_view(),
        name="booking-contact-detail",
    ),
    path("platform/bookings/", PlatformBookingListView.as_view(), name="platform-booking-list"),
    path(
        "platform/bookings/<uuid:booking_id>/",
        PlatformBookingDetailView.as_view(),
        name="platform-booking-detail",
    ),
    path("developer/bookings/", DeveloperBookingListView.as_view(), name="developer-booking-list"),
]
