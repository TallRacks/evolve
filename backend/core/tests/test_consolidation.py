import pytest

from artists.models import Artist
from contacts.models import Contact
from finance.models import Invoice
from organizations.models import Membership, Organization
from rights.models import Work
from users.models import User

pytestmark = pytest.mark.django_db
PASSWORD = "Test-only-consolidation-credential-123"


def user_with_role(organization, role, email):
    user = User.objects.create_user(email=email, password=PASSWORD)
    Membership.objects.create(organization=organization, user=user, role=role)
    return user


@pytest.fixture
def records():
    first = Organization.objects.create(name="First Search Org", slug="first-search")
    second = Organization.objects.create(name="Second Search Org", slug="second-search")
    owner = user_with_role(first, Membership.Role.OWNER, "search-owner@example.invalid")
    manager = user_with_role(first, Membership.Role.MANAGER, "search-manager@example.invalid")
    member = user_with_role(first, Membership.Role.MEMBER, "search-member@example.invalid")
    artist_user = user_with_role(first, Membership.Role.ARTIST, "search-artist@example.invalid")
    first_artist = Artist.objects.create(
        organization=first, stage_name="Needle Artist", slug="needle-artist"
    )
    Artist.objects.create(organization=second, stage_name="Needle Private", slug="needle-private")
    Contact.objects.create(
        organization=first,
        first_name="Needle",
        last_name="Contact",
        email="needle-contact@example.invalid",
    )
    Work.objects.create(organization=first, title="Needle Work", created_by=owner)
    Invoice.objects.create(
        organization=first,
        invoice_number="INV-NEEDLE",
        billed_to_name="Needle Customer",
        currency="ZAR",
        created_by=owner,
    )
    return first, second, owner, manager, member, artist_user, first_artist


def search(client, user, organization, query="Needle"):
    client.force_login(user)
    return client.get(f"/api/search/?q={query}&organization_id={organization.id}")


def test_search_authentication_limits_and_scoping(client, records):
    first, second, owner, _, _, _, _ = records
    assert client.get("/api/search/?q=Needle").status_code == 401
    client.force_login(owner)
    assert client.get("/api/search/?q=n").status_code == 400
    assert client.get("/api/search/?q=" + "x" * 101).status_code == 400
    assert client.get("/api/search/?q=Needle&organization_id=invalid").status_code == 400
    response = search(client, owner, first)
    assert response.status_code == 200
    payload = response.json()
    assert all(len(group["results"]) <= 6 for group in payload["groups"])
    assert "Needle Private" not in str(payload)
    assert "needle-contact@example.invalid" in str(payload)
    assert "billed_to" not in str(payload) and "amount" not in str(payload)
    assert search(client, owner, second).json()["groups"] == []


def test_search_role_privacy_staff_and_superuser(client, records):
    first, second, _, manager, member, artist_user, _ = records
    manager_payload = search(client, manager, first).json()
    member_payload = search(client, member, first).json()
    artist_payload = search(client, artist_user, first).json()
    assert "invoice" not in str(manager_payload).lower()
    assert "invoice" not in str(member_payload).lower()
    assert artist_payload["groups"] == []
    staff = User.objects.create_user(
        email="search-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    assert search(client, staff, first).status_code == 200
    assert search(client, staff, first).json()["groups"] == []
    superuser = User.objects.create_superuser(
        email="search-super@example.invalid", password=PASSWORD
    )
    client.force_login(superuser)
    response = client.get("/api/search/?q=Needle")
    assert response.status_code == 200
    assert "Needle Private" in str(response.json())


def test_dashboard_is_curated_and_role_aware(client, records):
    first, second, owner, manager, member, artist_user, _ = records
    client.force_login(owner)
    payload = client.get(f"/api/dashboard/?organization_id={first.id}").json()
    assert payload["organization"]["id"] == str(first.id)
    assert "draft_invoices" in payload["counts"]
    for user in (manager, member, artist_user):
        client.force_login(user)
        payload = client.get(f"/api/dashboard/?organization_id={first.id}").json()
        assert "draft_invoices" not in payload["counts"]
        assert str(second.id) not in str(payload)


def test_artist_360_scoping_and_privacy(client, records):
    first, second, owner, manager, _, artist_user, artist = records
    client.force_login(manager)
    response = client.get(f"/api/artists/{artist.id}/overview/")
    assert response.status_code == 200
    assert "amount" not in str(response.json()).lower()
    other_artist = Artist.objects.get(organization=second)
    assert client.get(f"/api/artists/{other_artist.id}/overview/").status_code == 404
    client.force_login(artist_user)
    assert client.get(f"/api/artists/{artist.id}/overview/").status_code == 403
    staff = User.objects.create_user(
        email="artist360-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get(f"/api/artists/{artist.id}/overview/").status_code == 404
    client.force_login(owner)
    assert client.get(f"/api/artists/{artist.id}/overview/").status_code == 200
