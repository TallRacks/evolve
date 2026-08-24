from django.urls import path

from .views import (
    ContactDetailView,
    ContactListView,
    PlatformContactDetailView,
    PlatformContactListView,
)

urlpatterns = [
    path("contacts/", ContactListView.as_view()),
    path("contacts/<uuid:contact_id>/", ContactDetailView.as_view()),
    path("platform/contacts/", PlatformContactListView.as_view()),
    path("platform/contacts/<uuid:contact_id>/", PlatformContactDetailView.as_view()),
]
