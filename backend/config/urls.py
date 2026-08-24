from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/auth/", include("users.api.urls")),
    path("api/", include("organizations.api.urls")),
    path("api/", include("audit.api.urls")),
]
