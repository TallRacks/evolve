from datetime import date

import pytest
from rest_framework.test import APIClient

from artists.models import Artist
from bookings.models import Booking
from organizations.models import Membership, Organization
from reporting.models import SavedReportView
from reporting.services import _safe_cell
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    organization = Organization.objects.create(name="Reports Org", slug="reports-org")
    user = User.objects.create_user("reports@example.test", "Test-only-report-password-123")
    Membership.objects.create(user=user, organization=organization, role=Membership.Role.OWNER)
    artist = Artist.objects.create(
        organization=organization, stage_name="Formula Artist", slug="formula"
    )
    Booking.objects.create(
        organization=organization,
        artist=artist,
        title="=unsafe title",
        event_date=date(2030, 1, 1),
    )
    client = APIClient()
    client.force_authenticate(user)
    return client, user, organization


def test_report_is_scoped_and_requires_source_permission(context):
    client, _, organization = context
    response = client.get(
        "/api/reports/", {"organization_id": organization.id, "report_key": "bookings"}
    )
    assert response.status_code == 200
    assert response.json()["summary"]["total"] == 1

    outsider = User.objects.create_user("outsider@example.test", "Test-only-report-password-123")
    client.force_authenticate(outsider)
    assert (
        client.get(
            "/api/reports/", {"organization_id": organization.id, "report_key": "bookings"}
        ).status_code
        == 404
    )


def test_saved_views_are_private_and_default_is_unique(context):
    client, user, organization = context
    first = client.post(
        "/api/reports/saved-views/",
        {
            "organization_id": str(organization.id),
            "report_key": "bookings",
            "name": "Mine",
            "filters": {},
            "is_default": True,
        },
        format="json",
    )
    assert first.status_code == 201
    second = client.post(
        "/api/reports/saved-views/",
        {
            "organization_id": str(organization.id),
            "report_key": "bookings",
            "name": "Other",
            "filters": {},
            "is_default": True,
        },
        format="json",
    )
    assert second.status_code == 201
    assert SavedReportView.objects.filter(user=user, is_default=True).count() == 1


def test_csv_formula_injection_is_neutralized(context):
    client, _, organization = context
    response = client.get(
        "/api/reports/export/", {"organization_id": organization.id, "report_key": "bookings"}
    )
    assert response.status_code == 200
    assert "'=unsafe title" in response.content.decode()
    for prefix in "=+-@":
        assert _safe_cell(prefix + "value").startswith("'")


def test_all_report_contracts_resolve(context):
    client, _, organization = context
    for report_key in (
        "bookings",
        "artists",
        "promoters",
        "venues",
        "production",
        "travel",
        "tasks",
        "finance",
        "contracts",
        "music",
        "campaigns",
        "rights",
        "royalties",
    ):
        response = client.get(
            "/api/reports/",
            {"organization_id": organization.id, "report_key": report_key},
        )
        assert response.status_code == 200, (report_key, response.content)


def test_saved_view_cannot_be_changed_to_unpermitted_source(context):
    client, _, organization = context
    manager = User.objects.create_user("manager@example.test", "Test-only-report-password-123")
    Membership.objects.create(user=manager, organization=organization, role=Membership.Role.MANAGER)
    client.force_authenticate(manager)
    created = client.post(
        "/api/reports/saved-views/",
        {
            "organization_id": str(organization.id),
            "report_key": "bookings",
            "name": "Booking view",
            "filters": {},
        },
        format="json",
    )
    assert created.status_code == 201
    denied = client.patch(
        f"/api/reports/saved-views/{created.json()['id']}/",
        {"report_key": "finance"},
        format="json",
    )
    assert denied.status_code == 403


def test_malformed_report_filter_returns_400(context):
    client, _, organization = context
    response = client.get(
        "/api/reports/",
        {
            "organization_id": organization.id,
            "report_key": "bookings",
            "artist": "not-a-uuid",
        },
    )
    assert response.status_code == 400
