from django.urls import path

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
    DocumentListView,
    LinkDetailView,
    LinkView,
    PlatformDocumentDetailView,
    PlatformDocumentListView,
    PortalDocumentsView,
    VersionView,
)

urlpatterns = [
    path("documents/", DocumentListView.as_view()),
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
    path("documents/<uuid:document_id>/links/", LinkView.as_view()),
    path("documents/<uuid:document_id>/links/<uuid:link_id>/", LinkDetailView.as_view()),
    path("artist-portal/documents/", PortalDocumentsView.as_view()),
    path("platform/documents/", PlatformDocumentListView.as_view()),
    path("platform/documents/<uuid:document_id>/", PlatformDocumentDetailView.as_view()),
    path("developer/documents/", DeveloperDocumentsView.as_view()),
]
