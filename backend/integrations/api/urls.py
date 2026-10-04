from django.urls import path

from .views import (
    EmailCollectionView,
    EmailDetailView,
    EmailSendTestView,
    EmailTestView,
    StorageCollectionView,
    StorageDetailView,
    StoragePolicyView,
    StorageTestView,
    AvailableGoogleWorkspaceView,
    GoogleDriveFilesView, GoogleDriveDownloadView,
    GoogleWorkspaceCollectionView, GoogleWorkspaceDetailView, GoogleWorkspaceOAuthCallbackView,
    GoogleWorkspaceOAuthStartView, MailboxGoogleOAuthStartView, GoogleWorkspaceTestView,
)

urlpatterns = [
    path("platform/google-workspace/", GoogleWorkspaceCollectionView.as_view()),
    path("platform/google-workspace/<uuid:pk>/", GoogleWorkspaceDetailView.as_view()),
    path("platform/google-workspace/<uuid:pk>/test/", GoogleWorkspaceTestView.as_view()),
    path("platform/google-workspace/<uuid:pk>/oauth/start/", GoogleWorkspaceOAuthStartView.as_view()),
    path("platform/google-workspace/callback/", GoogleWorkspaceOAuthCallbackView.as_view()),
    path("workspace/mailbox/google/start/", MailboxGoogleOAuthStartView.as_view()),
    path("platform/google-workspace/<uuid:pk>/<str:action>/", GoogleWorkspaceDetailView.as_view()),
    path("google-workspace/available/", AvailableGoogleWorkspaceView.as_view()),
    path("google-drive/files/", GoogleDriveFilesView.as_view()),
    path("google-drive/files/<str:file_id>/download/", GoogleDriveDownloadView.as_view()),
    path("platform/email-connectors/", EmailCollectionView.as_view()),
    path("platform/email-connectors/<uuid:pk>/", EmailDetailView.as_view()),
    path("platform/email-connectors/<uuid:pk>/test/", EmailTestView.as_view()),
    path("platform/email-connectors/<uuid:pk>/send-test/", EmailSendTestView.as_view()),
    path("platform/email-connectors/<uuid:pk>/<str:action>/", EmailDetailView.as_view()),
    path("platform/storage/", StorageCollectionView.as_view()),
    path("platform/storage/<uuid:pk>/", StorageDetailView.as_view()),
    path("platform/storage-policy/", StoragePolicyView.as_view()),
    path("platform/storage/<uuid:pk>/test/", StorageTestView.as_view()),
    path("platform/storage/<uuid:pk>/<str:action>/", StorageDetailView.as_view()),
]
