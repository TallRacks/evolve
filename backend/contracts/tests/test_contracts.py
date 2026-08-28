from datetime import date
from decimal import Decimal

import pytest
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError

from artists.models import Artist, ArtistPortalLink
from audit.models import AuditEvent
from bookings.models import Booking
from contracts.admin import ContractAdmin
from contracts.models import (
    Contract,
)
from contracts.services import (
    create_child,
    create_contract,
    create_from_booking,
    decide_approval,
    link_document,
    request_approval,
    set_signing_status,
    transition_contract,
    update_contract,
)
from documents.models import Document
from organizations.models import Membership, Organization
from promoters.models import Promoter
from users.models import User
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db
@pytest.fixture
def org():
    return Organization.objects.create(name="Contract Org", slug="contract-org")


@pytest.fixture
def other_org():
    return Organization.objects.create(name="Other Contract Org", slug="other-contract-org")


def role_user(org, role, email):
    user = User.objects.create_user(email=email, password=None)
    membership = Membership.objects.create(user=user, organization=org, role=role)
    return user, membership


@pytest.fixture
def owner(org):
    return role_user(org, Membership.Role.OWNER, "contract-owner@example.invalid")


@pytest.fixture
def manager(org):
    return role_user(org, Membership.Role.MANAGER, "contract-manager@example.invalid")


@pytest.fixture
def member(org):
    return role_user(org, Membership.Role.MEMBER, "contract-member@example.invalid")


@pytest.fixture
def artist(org):
    return Artist.objects.create(
        organization=org, stage_name="Contract Artist", slug="contract-artist"
    )


@pytest.fixture
def promoter(org):
    return Promoter.objects.create(
        organization=org, name="Contract Promoter", slug="contract-promoter"
    )


@pytest.fixture
def booking(org, artist, promoter):
    return Booking.objects.create(
        organization=org,
        artist=artist,
        promoter=promoter,
        title="Contract Show",
        event_date=date(2026, 12, 1),
        currency="ZAR",
        performance_fee=Decimal("50000.00"),
    )


@pytest.fixture
def contract(owner, org, artist, booking, promoter):
    return create_contract(
        actor=owner[0],
        organization=org,
        data={
            "title": "Performance agreement",
            "contract_type": "performance",
            "artist": artist,
            "booking": booking,
            "promoter": promoter,
            "effective_date": date(2026, 12, 1),
        },
    )


def test_create_uuid_reference_relationships_and_audit(contract):
    assert contract.reference.startswith("CTR-")
    assert contract.booking.artist == contract.artist
    assert AuditEvent.objects.filter(
        action="contract.created", resource_id=str(contract.id)
    ).exists()


def test_cross_organization_and_date_invariants(owner, org, other_org, artist):
    other_artist = Artist.objects.create(organization=other_org, stage_name="Other", slug="other")
    with pytest.raises(ValidationError):
        create_contract(
            actor=owner[0],
            organization=org,
            data={"title": "Invalid", "contract_type": "other", "artist": other_artist},
        )
    with pytest.raises(ValidationError):
        create_contract(
            actor=owner[0],
            organization=org,
            data={
                "title": "Invalid dates",
                "contract_type": "other",
                "effective_date": date(2027, 1, 2),
                "expiry_date": date(2027, 1, 1),
            },
        )


def test_party_snapshots_and_cross_org_rejection(owner, contract, other_org):
    party = create_child(
        "party",
        contract,
        actor=owner[0],
        data={"role": "artist", "linked_artist": contract.artist, "display_name": ""},
    )
    assert party.display_name == "Contract Artist"
    other = Artist.objects.create(organization=other_org, stage_name="Other", slug="other-party")
    with pytest.raises(ValidationError):
        create_child(
            "party",
            contract,
            actor=owner[0],
            data={"role": "artist", "linked_artist": other, "display_name": "Other"},
        )


def test_lifecycle_approvals_signing_execution_and_immutability(owner, contract):
    create_child(
        "term",
        contract,
        actor=owner[0],
        data={
            "term_type": "fee",
            "title": "Fee",
            "value_decimal": Decimal("50000.00"),
            "currency": "ZAR",
        },
    )
    party = create_child(
        "party",
        contract,
        actor=owner[0],
        data={
            "role": "artist",
            "display_name": "Artist Legal Entity",
            "is_signatory": True,
            "signing_status": "pending",
        },
    )
    contract = transition_contract(contract, actor=owner[0], to_status="in_review")
    approval = request_approval(contract, actor=owner[0], membership=owner[1])
    with pytest.raises(ValidationError):
        transition_contract(contract, actor=owner[0], to_status="approved")
    decide_approval(approval, actor=owner[0], decision="approved")
    contract = transition_contract(contract, actor=owner[0], to_status="approved")
    contract = transition_contract(contract, actor=owner[0], to_status="sent")
    with pytest.raises(ValidationError):
        transition_contract(contract, actor=owner[0], to_status="executed")
    set_signing_status(party, actor=owner[0], status="signed")
    contract.refresh_from_db()
    transition_contract(contract, actor=owner[0], to_status="executed")
    contract.refresh_from_db()
    assert contract.status == "executed"
    contract.title = "Changed"
    with pytest.raises(ValidationError):
        contract.save()
    term = contract.terms.first()
    term.title = "Changed"
    with pytest.raises(ValidationError):
        term.save()


def test_termination_requires_reason(owner, contract):
    Contract.objects.filter(pk=contract.pk).update(status="executed")
    contract.refresh_from_db()
    with pytest.raises(ValidationError):
        transition_contract(contract, actor=owner[0], to_status="terminated")
    contract = transition_contract(
        contract, actor=owner[0], to_status="terminated", reason="Agreement ended"
    )
    assert contract.termination_reason == "Agreement ended"


def test_approval_is_assignee_only(owner, manager, contract):
    contract = transition_contract(contract, actor=owner[0], to_status="in_review")
    approval = request_approval(contract, actor=owner[0], membership=owner[1])
    with pytest.raises(PermissionDenied):
        decide_approval(approval, actor=manager[0], decision="approved")


def test_document_link_is_organization_scoped(owner, contract, other_org):
    document = Document.objects.create(
        organization=contract.organization,
        title="Agreement",
        document_type="contract",
        external_url="https://example.invalid/agreement",
        uploaded_by=owner[0],
    )
    assert link_document(contract, actor=owner[0], document=document)
    other = Document.objects.create(
        organization=other_org,
        title="Other",
        document_type="contract",
        external_url="https://example.invalid/other",
        uploaded_by=owner[0],
    )
    with pytest.raises(ValidationError):
        link_document(contract, actor=owner[0], document=other)


def test_booking_creation_is_explicit_and_does_not_create_finance(owner, booking):
    row = create_from_booking(actor=owner[0], booking=booking)
    assert row.artist == booking.artist and row.status == "draft"
    assert row.terms.get().value_decimal == Decimal("50000.00")
    assert not hasattr(row, "invoice")


def test_api_org_isolation_staff_no_bypass_and_superuser(client, owner, member, contract):
    client.force_login(member[0])
    assert client.get(f"/api/contracts/{contract.id}/").status_code == 404
    staff = User.objects.create_user(email="staff-contract@example.invalid", is_staff=True)
    client.force_login(staff)
    assert client.get(f"/api/contracts/{contract.id}/").status_code == 404
    root = User.objects.create_superuser(email="root-contract@example.invalid", password=None)
    client.force_login(root)
    assert client.get(f"/api/contracts/{contract.id}/").status_code == 200
    request = type("Request", (), {"user": staff})()
    assert not ContractAdmin(Contract, admin.site).has_view_permission(request)


def test_artist_and_developer_responses_are_curated(client, owner, org, artist, contract):
    artist_user, _ = role_user(org, Membership.Role.ARTIST, "portal-contract@example.invalid")
    ArtistPortalLink.objects.create(artist=artist, user=artist_user)
    client.force_login(artist_user)
    assert client.get("/api/artist/contracts/").json() == []
    Contract.objects.filter(pk=contract.pk).update(
        status="executed", internal_notes="private legal note"
    )
    response = client.get("/api/artist/contracts/")
    assert response.status_code == 200 and len(response.json()) == 1
    assert not (
        {"internal_notes", "terms", "parties", "total_value", "promoter", "counterparty"}
        & response.json()[0].keys()
    )
    _, key = create_api_client_key(
        organization=org,
        name="Contracts",
        description="",
        scopes=["contract.read"],
        created_by=owner[0],
    )
    response = client.get("/api/developer/contracts/", HTTP_AUTHORIZATION=f"Bearer {key.secret}")
    assert response.status_code == 200
    assert not ({"internal_notes", "terms", "parties", "total_value"} & response.json()[0].keys())


def test_generic_update_cannot_change_status_and_audit_has_no_legal_content(owner, contract):
    update_contract(
        contract, actor=owner[0], data={"status": "executed", "summary": "Confidential body"}
    )
    contract.refresh_from_db()
    assert contract.status == "draft"
    descriptions = " ".join(
        AuditEvent.objects.filter(resource_id=str(contract.id)).values_list(
            "description", flat=True
        )
    )
    assert "Confidential body" not in descriptions
