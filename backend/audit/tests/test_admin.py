import pytest
from django.contrib import admin
from django.test import RequestFactory

from audit.admin import AuditEventAdmin
from audit.models import AuditEvent

pytestmark = pytest.mark.django_db


def test_audit_admin_is_read_only(superuser):
    model_admin = AuditEventAdmin(AuditEvent, admin.site)
    request = RequestFactory().get("/admin/audit/auditevent/")
    request.user = superuser
    assert model_admin.has_view_permission(request)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)
