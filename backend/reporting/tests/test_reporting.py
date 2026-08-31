from datetime import date

import pytest
from rest_framework.test import APIClient

from artists.models import Artist
from bookings.models import Booking
from music.models import Release
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


def test_summary_uses_full_filtered_dataset_and_rows_are_paginated(context):
    client, _, organization = context
    artist = Artist.objects.get(organization=organization)
    Booking.objects.bulk_create(
        [
            Booking(
                organization=organization,
                artist=artist,
                title=f"Booking {index}",
                event_date=date(2030, 1, 2),
            )
            for index in range(30)
        ]
    )
    response = client.get(
        "/api/reports/bookings/",
        {"organization_id": organization.id, "page_size": 10, "page": 2},
    )
    assert response.status_code == 200
    assert response.json()["summary"]["total"] == 31
    assert response.json()["pagination"] == {
        "page": 2,
        "page_size": 10,
        "pages": 4,
        "total": 31,
    }
    assert len(response.json()["rows"]) == 10


def test_report_rejects_invalid_date_range_and_sort(context):
    client, _, organization = context
    invalid_range = client.get(
        "/api/reports/bookings/",
        {
            "organization_id": organization.id,
            "date_from": "2030-02-01",
            "date_to": "2030-01-01",
        },
    )
    assert invalid_range.status_code == 400
    invalid_sort = client.get(
        "/api/reports/bookings/",
        {"organization_id": organization.id, "sort": "artist__organization"},
    )
    assert invalid_sort.status_code == 400


def test_empty_export_has_allowlisted_headers(context):
    client, _, organization = context
    response = client.get(
        "/api/reports/bookings/export/",
        {"organization_id": organization.id, "status": "does-not-exist"},
    )
    assert response.status_code == 200
    assert response.content.decode().startswith("reference,title,artist,date,status,priority")


def test_saved_view_is_not_accessible_to_another_user(context):
    client, _, organization = context
    created = client.post(
        "/api/reports/saved-views/",
        {
            "organization_id": str(organization.id),
            "report_key": "bookings",
            "name": "Private",
            "filters": {},
        },
        format="json",
    )
    other = User.objects.create_user("other@example.test", "Test-only-report-password-123")
    Membership.objects.create(user=other, organization=organization, role=Membership.Role.OWNER)
    client.force_authenticate(other)
    assert (
        client.patch(
            f"/api/reports/saved-views/{created.json()['id']}/",
            {"name": "Taken"},
            format="json",
        ).status_code
        == 404
    )


def test_music_report_uses_planned_release_date(context):
    client, _, organization = context
    artist = Artist.objects.get(organization=organization)
    Release.objects.create(
        organization=organization,
        primary_artist=artist,
        title="Scheduled release",
        slug="scheduled-release",
        release_type=Release.Type.SINGLE,
        planned_release_date=date(2030, 3, 1),
    )
    response = client.get(
        "/api/reports/music/",
        {
            "organization_id": organization.id,
            "date_from": "2030-01-01",
            "date_to": "2030-12-31",
        },
    )
    assert response.status_code == 200
    assert response.json()["rows"][0]["release_date"] == "2030-03-01"


def test_report_rejects_filter_not_registered_for_report(context):
    client, _, organization = context
    response = client.get(
        "/api/reports/finance/",
        {"organization_id": organization.id, "priority": "urgent"},
    )
    assert response.status_code == 400
