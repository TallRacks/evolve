from django.urls import path

from .views import (
    AdvanceDetailView,
    AdvanceListView,
    AdvanceStatusView,
    ArtistProductionView,
    ChecklistCompletionView,
    ChildDetailView,
    ChildListView,
    ChildReorderView,
    ChildStatusView,
    DeveloperProductionView,
    PlatformAdvanceDetailView,
    PlatformAdvanceListView,
)


def child_view(base, kind):
    cls = type(f"{kind.title()}{base.__name__}", (base,), {"kind": kind})
    return cls.as_view()


urlpatterns = [
    path("production/advances/", AdvanceListView.as_view()),
    path("production/advances/<uuid:advance_id>/", AdvanceDetailView.as_view()),
    path("production/advances/<uuid:advance_id>/status/", AdvanceStatusView.as_view()),
    path(
        "production/advances/<uuid:advance_id>/requirements/",
        child_view(ChildListView, "requirement"),
    ),
    path("production/advances/<uuid:advance_id>/contacts/", child_view(ChildListView, "contact")),
    path("production/advances/<uuid:advance_id>/schedule/", child_view(ChildListView, "schedule")),
    path(
        "production/advances/<uuid:advance_id>/checklist/", child_view(ChildListView, "checklist")
    ),
    path("production/requirements/<uuid:child_id>/", child_view(ChildDetailView, "requirement")),
    path(
        "production/requirements/<uuid:child_id>/status/",
        child_view(ChildStatusView, "requirement"),
    ),
    path(
        "production/requirements/<uuid:child_id>/reorder/",
        child_view(ChildReorderView, "requirement"),
    ),
    path("production/contacts/<uuid:child_id>/", child_view(ChildDetailView, "contact")),
    path("production/schedule/<uuid:child_id>/", child_view(ChildDetailView, "schedule")),
    path("production/schedule/<uuid:child_id>/status/", child_view(ChildStatusView, "schedule")),
    path("production/schedule/<uuid:child_id>/reorder/", child_view(ChildReorderView, "schedule")),
    path("production/checklist/<uuid:child_id>/", child_view(ChildDetailView, "checklist")),
    path("production/checklist/<uuid:child_id>/complete/", ChecklistCompletionView.as_view()),
    path(
        "production/checklist/<uuid:child_id>/reopen/",
        type("ChecklistReopenView", (ChecklistCompletionView,), {"completed": False}).as_view(),
    ),
    path(
        "production/checklist/<uuid:child_id>/reorder/", child_view(ChildReorderView, "checklist")
    ),
    path("artist/production/", ArtistProductionView.as_view()),
    path("platform/production/", PlatformAdvanceListView.as_view()),
    path("platform/production/<uuid:advance_id>/", PlatformAdvanceDetailView.as_view()),
    path("developer/production/advances/", DeveloperProductionView.as_view()),
]
