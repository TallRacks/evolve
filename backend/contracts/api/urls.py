from django.urls import path

from .views import (
    ApprovalDecisionView,
    ApprovalListView,
    ArtistContractView,
    BookingContractCreateView,
    ChildDetailView,
    ChildListView,
    ContractDetailView,
    ContractListView,
    ContractStatusView,
    DeveloperContractView,
    DocumentDetailView,
    DocumentListView,
    ContractDocumentUploadView,
    PlatformContractDetailView,
    PlatformContractListView,
    SigningView,
)


def child(base, kind):
    return type(f"{kind.title()}{base.__name__}", (base,), {"kind": kind}).as_view()


urlpatterns = [
    path("contracts/", ContractListView.as_view()),
    path("contracts/<uuid:contract_id>/", ContractDetailView.as_view()),
    path("contracts/<uuid:contract_id>/status/", ContractStatusView.as_view()),
    path("contracts/<uuid:contract_id>/parties/", child(ChildListView, "party")),
    path("contracts/<uuid:contract_id>/terms/", child(ChildListView, "term")),
    path("contracts/<uuid:contract_id>/sections/", child(ChildListView, "section")),
    path("contract-parties/<uuid:child_id>/", child(ChildDetailView, "party")),
    path("contract-parties/<uuid:party_id>/signing-status/", SigningView.as_view()),
    path("contract-terms/<uuid:child_id>/", child(ChildDetailView, "term")),
    path("contract-sections/<uuid:child_id>/", child(ChildDetailView, "section")),
    path("contracts/<uuid:contract_id>/approvals/", ApprovalListView.as_view()),
    path("contract-approvals/<uuid:approval_id>/decision/", ApprovalDecisionView.as_view()),
    path("contracts/<uuid:contract_id>/documents/", DocumentListView.as_view()),
    path("contracts/<uuid:contract_id>/documents/upload/", ContractDocumentUploadView.as_view()),
    path("contract-documents/<uuid:link_id>/", DocumentDetailView.as_view()),
    path("bookings/<uuid:booking_id>/contracts/create/", BookingContractCreateView.as_view()),
    path("artist/contracts/", ArtistContractView.as_view()),
    path("platform/contracts/", PlatformContractListView.as_view()),
    path("platform/contracts/<uuid:contract_id>/", PlatformContractDetailView.as_view()),
    path("developer/contracts/", DeveloperContractView.as_view()),
]
