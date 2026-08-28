from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/auth/", include("users.api.urls")),
    path("api/", include("organizations.api.urls")),
    path("api/", include("artists.api.urls")),
    path("api/", include("bookings.api.urls")),
    path("api/", include("callsheets.api.urls")),
    path("api/", include("music.api.urls")),
    path("api/", include("campaigns.api.urls")),
    path("api/", include("calendar_app.api.urls")),
    path("api/", include("documents.api.urls")),
    path("api/", include("notifications.api.urls")),
    path("api/", include("finance.api.urls")),
    path("api/", include("rights.api.urls")),
    path("api/", include("travel.api.urls")),
    path("api/", include("production.api.urls")),
    path("api/", include("contracts.api.urls")),
    path("api/", include("contacts.api.urls")),
    path("api/", include("promoters.api.urls")),
    path("api/", include("venues.api.urls")),
    path("api/", include("audit.api.urls")),
    path("api/", include("white_label.api.urls")),
]
