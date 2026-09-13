from django.urls import path

from documents.api.generator_api import BookingOfficeGeneratorView, ReleaseOfficeGeneratorView
from documents.api.office_api import (
    OfficeAttachmentContentView,
    OfficeAttachmentView,
    OfficeContentView,
    OfficeDocumentCollectionView,
    OfficeDocumentListView,
    OfficeRevisionView,
    OfficeSheetExportView,
    OfficeSheetView,
    OfficeTaskView,
)
from documents.template_api import (
    TemplateActionView,
    TemplateDetailView,
    TemplateGenerateView,
    TemplateListView,
    TemplatePreviewView,
    TemplateSectionDetailView,
    TemplateSectionView,
)

from .views import (
    ArchiveView,
    DeveloperDocumentsView,
    DocumentDetailView,
    DocumentDownloadView,
    DocumentListView,
    DocumentPreviewView,
    DocumentUploadView,
    LinkDetailView,
    LinkView,
    PlatformDocumentDetailView,
    PlatformDocumentListView,
    PortalDocumentsView,
    StorageStatusView,
    VersionUploadView,
    VersionView,
)

urlpatterns = [
    path(
        "bookings/<uuid:booking_id>/office/<slug:generator>/", BookingOfficeGeneratorView.as_view()
    ),
    path(
        "music/releases/<uuid:release_id>/office/<slug:generator>/",
        ReleaseOfficeGeneratorView.as_view(),
    ),
    path("office/documents/", OfficeDocumentCollectionView.as_view()),
    path("office/documents/list/", OfficeDocumentListView.as_view()),
    path("documents/<uuid:document_id>/office-content/", OfficeContentView.as_view()),
    path("documents/<uuid:document_id>/office-revisions/", OfficeRevisionView.as_view()),
    path("documents/<uuid:document_id>/office-attachments/", OfficeAttachmentView.as_view()),
    path(
        "documents/<uuid:document_id>/office-attachments/<uuid:attachment_id>/",
        OfficeAttachmentView.as_view(),
    ),
    path(
        "documents/<uuid:document_id>/office-attachments/<uuid:attachment_id>/preview/",
        OfficeAttachmentContentView.as_view(),
    ),
    path("documents/<uuid:document_id>/office-task/", OfficeTaskView.as_view()),
    path("documents/<uuid:document_id>/office-sheet/", OfficeSheetView.as_view()),
    path("documents/<uuid:document_id>/office-sheet/export/", OfficeSheetExportView.as_view()),
    path(
        "documents/<uuid:document_id>/office-revisions/<int:revision_number>/restore/",
        OfficeRevisionView.as_view(),
    ),
    path("documents/", DocumentListView.as_view()),
    path("documents/upload/", DocumentUploadView.as_view()),
    path("documents/storage-status/", StorageStatusView.as_view()),
    path("document-templates/", TemplateListView.as_view()),
    path("document-templates/<uuid:template_id>/", TemplateDetailView.as_view()),
    path("document-templates/<uuid:template_id>/sections/", TemplateSectionView.as_view()),
    path(
        "document-templates/<uuid:template_id>/sections/<uuid:section_id>/",
        TemplateSectionDetailView.as_view(),
    ),
    path("document-templates/<uuid:template_id>/preview/", TemplatePreviewView.as_view()),
    path("document-templates/<uuid:template_id>/generate/", TemplateGenerateView.as_view()),
    path("document-templates/<uuid:template_id>/<slug:action>/", TemplateActionView.as_view()),
    path("documents/<uuid:document_id>/", DocumentDetailView.as_view()),
    path("documents/<uuid:document_id>/archive/", ArchiveView.as_view()),
    path("documents/<uuid:document_id>/versions/", VersionView.as_view()),
    path("documents/<uuid:document_id>/versions/upload/", VersionUploadView.as_view()),
    path("documents/<uuid:document_id>/download/", DocumentDownloadView.as_view()),
    path("documents/<uuid:document_id>/preview/", DocumentPreviewView.as_view()),
    path("documents/<uuid:document_id>/links/", LinkView.as_view()),
    path("documents/<uuid:document_id>/links/<uuid:link_id>/", LinkDetailView.as_view()),
    path("artist-portal/documents/", PortalDocumentsView.as_view()),
    path("platform/documents/", PlatformDocumentListView.as_view()),
    path("platform/documents/<uuid:document_id>/", PlatformDocumentDetailView.as_view()),
    path("developer/documents/", DeveloperDocumentsView.as_view()),
]
