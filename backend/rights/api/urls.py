from django.urls import path

from . import views

urlpatterns = [
    path("rights/works/", views.WorkListCreate.as_view()),
    path("rights/works/<uuid:pk>/", views.WorkDetail.as_view()),
    path("rights/works/<uuid:pk>/archive/", views.WorkArchive.as_view()),
    path("rights/works/<uuid:pk>/tracks/", views.WorkTrack.as_view()),
    path("rights/works/<uuid:pk>/contributors/", views.WorkContributorView.as_view()),
    path("rights/works/<uuid:pk>/publishing/", views.PublishingView.as_view()),
    path("rights/parties/", views.PartyListCreate.as_view()),
    path("rights/masters/", views.MasterListCreate.as_view()),
    path("rights/overview/", views.RightsOverview.as_view()),
    path("royalties/statements/", views.StatementListCreate.as_view()),
    path("royalties/advances/", views.RoyaltyAdvanceListCreate.as_view()),
    path("royalties/advances/<uuid:pk>/", views.RoyaltyAdvanceDetail.as_view()),
    path("royalties/sources/", views.RoyaltySourceListCreate.as_view()),
    path("royalties/statements/<uuid:pk>/map-catalog/", views.RoyaltyCatalogMapView.as_view()),
    path("royalties/statements/<uuid:pk>/", views.StatementDetail.as_view()),
    path("royalties/statements/<uuid:pk>/lines/", views.StatementLineView.as_view()),
    path("royalties/statements/<uuid:pk>/import/", views.StatementImportView.as_view()),
    path("royalties/statements/<uuid:pk>/finalize/", views.StatementFinalize.as_view()),
    path("royalties/statements/<uuid:pk>/void/", views.StatementVoid.as_view()),
    path("royalties/lines/<uuid:pk>/generate/", views.GenerateView.as_view()),
    path(
        "royalties/lines/<uuid:pk>/allocations/", views.ManualAllocationView.as_view()
    ),
    path("royalties/allocations/<uuid:pk>/", views.ManualAllocationDetail.as_view()),
    path("platform/rights/works/", views.PlatformWorks.as_view()),
    path("platform/royalties/statements/", views.PlatformStatements.as_view()),
    path("artist-portal/rights/", views.ArtistRights.as_view()),
    path("developer/rights/works/", views.DeveloperWorks.as_view()),
    path("developer/rights/tracks/", views.DeveloperTracks.as_view()),
]
