from django.urls import path

from .views import (
    DeveloperPromoterListView,
    PlatformPromoterDetailView,
    PlatformPromoterListView,
    PromoterContactDetailView,
    PromoterContactsView,
    PromoterDetailView,
    PromoterListView,
)

urlpatterns = [
    path("promoters/", PromoterListView.as_view()),
    path("promoters/<uuid:promoter_id>/", PromoterDetailView.as_view()),
    path("promoters/<uuid:promoter_id>/contacts/", PromoterContactsView.as_view()),
    path(
        "promoters/<uuid:promoter_id>/contacts/<uuid:link_id>/", PromoterContactDetailView.as_view()
    ),
    path("platform/promoters/", PlatformPromoterListView.as_view()),
    path("platform/promoters/<uuid:promoter_id>/", PlatformPromoterDetailView.as_view()),
    path("developer/promoters/", DeveloperPromoterListView.as_view()),
]
