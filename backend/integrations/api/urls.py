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
)

urlpatterns = [
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
