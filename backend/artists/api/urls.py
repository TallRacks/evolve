from django.urls import path

from .views import (
    Artist360View,
    ArtistDetailView,
    ArtistListView,
    ArtistPortalLinkDetailView,
    ArtistPortalLinksView,
    ArtistPortalView,
    ArtistTeamDetailView,
    ArtistTeamView,
    ArtistToolkitView,
    DeveloperArtistListView,
    PlatformArtistDetailView,
    PlatformArtistListView,
)

urlpatterns = [
    path("artists/", ArtistListView.as_view(), name="artist-list"),
    path("artists/<uuid:artist_id>/", ArtistDetailView.as_view(), name="artist-detail"),
    path("artists/<uuid:artist_id>/overview/", Artist360View.as_view(), name="artist-overview"),
    path("artists/<uuid:artist_id>/toolkit/", ArtistToolkitView.as_view(), name="artist-toolkit"),
    path("artists/<uuid:artist_id>/team/", ArtistTeamView.as_view(), name="artist-team"),
    path(
        "artists/<uuid:artist_id>/team/<uuid:assignment_id>/",
        ArtistTeamDetailView.as_view(),
        name="artist-team-detail",
    ),
    path(
        "artists/<uuid:artist_id>/portal-links/",
        ArtistPortalLinksView.as_view(),
        name="artist-portal-links",
    ),
    path(
        "artists/<uuid:artist_id>/portal-links/<uuid:link_id>/unlink/",
        ArtistPortalLinkDetailView.as_view(),
        name="artist-portal-link-detail",
    ),
    path("artist-portal/", ArtistPortalView.as_view(), name="artist-portal"),
    path(
        "platform/artists/",
        PlatformArtistListView.as_view(),
        name="platform-artist-list",
    ),
    path(
        "platform/artists/<uuid:artist_id>/",
        PlatformArtistDetailView.as_view(),
        name="platform-artist-detail",
    ),
    path(
        "developer/artists/",
        DeveloperArtistListView.as_view(),
        name="developer-artist-list",
    ),
]
