from django.urls import path

from .views import OpenSignWebhookView, SigningEventListView, SigningRequestActionView, SigningRequestDetailView, SigningRequestListView

urlpatterns = [
    path("signing/requests/", SigningRequestListView.as_view()),
    path("signing/requests/<uuid:request_id>/", SigningRequestDetailView.as_view()),
    path("signing/requests/<uuid:request_id>/action/", SigningRequestActionView.as_view()),
    path("signing/requests/<uuid:request_id>/events/", SigningEventListView.as_view()),
    path("integrations/opensign/webhook/", OpenSignWebhookView.as_view()),
    path("integrations/opensign/webhook/<uuid:request_id>/", OpenSignWebhookView.as_view()),
]
