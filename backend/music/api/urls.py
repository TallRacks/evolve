from django.urls import path

from music.models import Release, Track

from .views import (
    ArtistPortalMusicView,
    CreditDetailView,
    CreditListView,
    DeveloperMusicView,
    LinkDetailView,
    LinkListView,
    PlatformReleaseDetailView,
    PlatformReleaseListView,
    PlatformTrackDetailView,
    PlatformTrackListView,
    ReleaseDetailView,
    ReleaseListView,
    ReleaseStatusView,
    ReleaseTrackDetailView,
    ReleaseTracksView,
    TrackDetailView,
    TrackListView,
)

urlpatterns = [
    path("music/releases/", ReleaseListView.as_view()),
    path("music/releases/<uuid:release_id>/", ReleaseDetailView.as_view()),
    path("music/releases/<uuid:release_id>/status/", ReleaseStatusView.as_view()),
    path("music/releases/<uuid:release_id>/tracks/", ReleaseTracksView.as_view()),
    path(
        "music/releases/<uuid:release_id>/tracks/<uuid:placement_id>/",
        ReleaseTrackDetailView.as_view(),
    ),
    path(
        "music/releases/<uuid:resource_id>/credits/",
        CreditListView.as_view(resource_type="release"),
    ),
    path(
        "music/releases/<uuid:resource_id>/credits/<uuid:credit_id>/",
        CreditDetailView.as_view(resource_type="release"),
    ),
    path("music/releases/<uuid:release_id>/links/", LinkListView.as_view()),
    path("music/releases/<uuid:release_id>/links/<uuid:link_id>/", LinkDetailView.as_view()),
    path("music/tracks/", TrackListView.as_view()),
    path("music/tracks/<uuid:track_id>/", TrackDetailView.as_view()),
    path("music/tracks/<uuid:resource_id>/credits/", CreditListView.as_view(resource_type="track")),
    path(
        "music/tracks/<uuid:resource_id>/credits/<uuid:credit_id>/",
        CreditDetailView.as_view(resource_type="track"),
    ),
    path("artist-portal/music/", ArtistPortalMusicView.as_view()),
    path("platform/music/releases/", PlatformReleaseListView.as_view()),
    path("platform/music/releases/<uuid:release_id>/", PlatformReleaseDetailView.as_view()),
    path("platform/music/tracks/", PlatformTrackListView.as_view()),
    path("platform/music/tracks/<uuid:track_id>/", PlatformTrackDetailView.as_view()),
    path("developer/releases/", DeveloperMusicView.as_view(model=Release)),
    path("developer/tracks/", DeveloperMusicView.as_view(model=Track)),
]
