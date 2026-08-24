import pytest
from django.contrib import admin
from django.test import RequestFactory

from organizations.admin import OrganizationAdmin
from organizations.models import Organization
from users.models import User

pytestmark = pytest.mark.django_db


def test_platform_models_admin_requires_superuser(superuser):
    model_admin = OrganizationAdmin(Organization, admin.site)
    request = RequestFactory().get("/admin/")
    request.user = superuser
    assert model_admin.has_module_permission(request)

    request.user = User.objects.create_user(
        email="staff@example.com", password="Correct-Horse-123", is_staff=True
    )
    assert not model_admin.has_module_permission(request)
    assert not model_admin.has_view_permission(request)
