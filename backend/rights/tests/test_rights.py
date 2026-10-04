from datetime import date
from decimal import Decimal
from io import BytesIO
from threading import Barrier, Thread
from zipfile import ZipFile

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections

from artists.models import Artist, ArtistPortalLink
from contacts.models import Contact
from music.models import Track
from organizations.models import Membership, Organization
from rights.import_services import _xlsx_rows
from rights.models import MasterRight, RightsParty, RoyaltySource, RoyaltyStatement, Work
from rights.services import (
    add_master_right,
    add_publishing_right,
    add_statement_line,
    allocate_manual,
    create_party,
    create_statement,
    create_work,
    finalize_statement,
    generate_allocations,
    link_track,
    update_manual_allocation,
    update_statement,
    void_statement,
)
from users.models import User
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db(transaction=True)
PASSWORD = "Test-only-rights-credential-123"


def member(organization, role, email):
    user = User.objects.create_user(email=email, password=PASSWORD)
    Membership.objects.create(organization=organization, user=user, role=role)
    return user


@pytest.fixture
def foundation():
    organization = Organization.objects.create(name="Rights Org", slug="rights-org")
    owner = member(organization, Membership.Role.OWNER, "rights-owner@example.invalid")
    manager = member(
        organization, Membership.Role.MANAGER, "rights-manager@example.invalid"
    )
    artist_user = member(
        organization, Membership.Role.ARTIST, "rights-artist@example.invalid"
    )
    artist = Artist.objects.create(
        organization=organization,
        stage_name="Rights Artist",
        slug="rights-artist",
    )
    ArtistPortalLink.objects.create(artist=artist, user=artist_user)
    track = Track.objects.create(
        organization=organization,
        primary_artist=artist,
        title="Recorded Song",
        slug="recorded-song",
        created_by=owner,
    )
    return organization, owner, manager, artist_user, artist, track


def party(owner, organization, artist=None, name="Writer"):
    return create_party(
        actor=owner,
        organization=organization,
        data={
            "party_type": RightsParty.Type.ARTIST
            if artist
            else RightsParty.Type.SONGWRITER,
            "display_name": name,
            "linked_artist": artist,
        },
    )


def statement_line(foundation, basis="master", amount="100.00"):
    organization, owner, _, _, artist, track = foundation
    source = RoyaltySource.objects.create(
        organization=organization,
        name="Test distributor",
        source_type=RoyaltySource.Type.DISTRIBUTOR,
    )
    statement = create_statement(
        actor=owner,
        organization=organization,
        data={
            "source_name": "Test distributor",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "currency": "ZAR",
            "declared_total": Decimal(amount),
        },
    )
    assert statement.source_id == source.id
    line = add_statement_line(
        actor=owner,
        statement=statement,
        data={
            "track": track,
            "artist": artist,
            "rights_basis": basis,
            "gross_amount": Decimal(amount),
            "deductions": Decimal("0"),
        },
    )
    return statement, line


def test_work_party_contributor_boundary_and_identifiers(foundation):
    organization, owner, _, _, artist, track = foundation
    work = create_work(
        actor=owner,
        organization=organization,
        data={"title": "Composition", "iswc": "t-123.456.789-0"},
    )
    assert work.id and work.iswc == "T1234567890"
    link_track(actor=owner, work=work, track=track, relationship_type="primary")
    rights_party = party(owner, organization, artist)
    assert rights_party.linked_artist == artist
    assert not hasattr(rights_party, "user")
    assert work.track_links.get().track == track

    other = Organization.objects.create(name="Other", slug="rights-other")
    contact = Contact.objects.create(
        organization=other, first_name="Other", last_name="Contact"
    )
    with pytest.raises(ValidationError):
        RightsParty(
            organization=organization,
            party_type="other",
            display_name="Invalid",
            linked_contact=contact,
        ).save()


def test_split_totals_dates_territories_and_incomplete_allowed(foundation):
    organization, owner, _, _, _, track = foundation
    first = party(owner, organization, name="Writer One")
    second = party(owner, organization, name="Writer Two")
    master = add_master_right(
        actor=owner,
        track=track,
        data={
            "party": first,
            "ownership_percentage": Decimal("60"),
            "territory_code": "WORLDWIDE",
        },
    )
    assert master.ownership_percentage == 60
    with pytest.raises(ValidationError):
        add_master_right(
            actor=owner,
            track=track,
            data={
                "party": second,
                "ownership_percentage": Decimal("41"),
                "territory_code": "ZA",
            },
        )
    add_master_right(
        actor=owner,
        track=track,
        data={
            "party": second,
            "ownership_percentage": Decimal("40"),
            "territory_code": "ZA",
            "effective_from": date(2027, 1, 1),
        },
    )
    with pytest.raises(ValidationError):
        MasterRight(
            organization=organization,
            track=track,
            party=second,
            ownership_percentage=1,
            effective_from=date(2026, 2, 1),
            effective_to=date(2026, 1, 1),
        ).full_clean()

    work = create_work(actor=owner, organization=organization, data={"title": "Work"})
    add_publishing_right(
        actor=owner,
        work=work,
        data={
            "party": first,
            "right_type": "writer",
            "ownership_percentage": Decimal("70"),
        },
    )
    with pytest.raises(ValidationError):
        add_publishing_right(
            actor=owner,
            work=work,
            data={
                "party": second,
                "right_type": "publisher",
                "ownership_percentage": Decimal("31"),
            },
        )


def test_royalty_decimal_allocation_finalize_void_and_snapshot(foundation):
    organization, owner, _, _, artist, track = foundation
    artist_party = party(owner, organization, artist, "Artist Party")
    other_party = party(owner, organization, name="Label")
    add_master_right(
        actor=owner,
        track=track,
        data={"party": artist_party, "ownership_percentage": Decimal("33.3333")},
    )
    add_master_right(
        actor=owner,
        track=track,
        data={"party": other_party, "ownership_percentage": Decimal("66.6667")},
    )
    statement, line = statement_line(foundation, amount="10.00")
    allocations = generate_allocations(actor=owner, line=line)
    assert sum((item.amount for item in allocations), Decimal("0")) == Decimal("10.00")
    statement = finalize_statement(actor=owner, statement=statement)
    assert statement.status == RoyaltyStatement.Status.FINALIZED
    before = list(line.allocations.values_list("amount", flat=True))
    with pytest.raises(ValidationError):
        line.gross_amount = Decimal("20")
        line.save()
    assert list(line.allocations.values_list("amount", flat=True)) == before
    statement = void_statement(
        actor=owner, statement=statement, reason="Replacement required"
    )
    assert statement.status == RoyaltyStatement.Status.VOID
    with pytest.raises(ValidationError):
        statement.delete()


def test_manual_allocation_and_reconciliation(foundation):
    organization, owner, _, _, artist, _ = foundation
    rights_party = party(owner, organization, artist)
    statement, line = statement_line(foundation, basis="other")
    allocation = allocate_manual(
        actor=owner,
        line=line,
        party=rights_party,
        percentage=Decimal("50"),
        amount=Decimal("50"),
    )
    update_statement(
        actor=owner,
        statement=statement,
        data={"source_name": "Edited distributor"},
    )
    allocation = update_manual_allocation(
        actor=owner,
        allocation=allocation,
        party=rights_party,
        percentage=Decimal("49"),
        amount=Decimal("49"),
    )
    assert allocation.amount == Decimal("49")
    with pytest.raises(ValidationError):
        allocate_manual(
            actor=owner,
            line=line,
            party=party(owner, organization, name="Other"),
            percentage=Decimal("52"),
            amount=Decimal("52"),
        )
    with pytest.raises(ValidationError):
        finalize_statement(actor=owner, statement=statement)
    assert statement.calculated_total == Decimal("100.00")
    assert statement.variance == Decimal("0.00")


def test_permissions_artist_privacy_staff_and_developer_api(client, foundation):
    organization, owner, manager, artist_user, artist, _ = foundation
    artist_party = party(owner, organization, artist)
    unrelated = Artist.objects.create(
        organization=organization, stage_name="Other Artist", slug="other-artist"
    )
    party(owner, organization, unrelated, "Private Other")
    with pytest.raises(PermissionDenied):
        create_work(actor=manager, organization=organization, data={"title": "Denied"})
    client.force_login(manager)
    assert (
        client.get(f"/api/rights/works/?organization_id={organization.id}").status_code
        == 403
    )
    client.force_login(artist_user)
    response = client.get("/api/artist-portal/rights/")
    assert response.status_code == 200
    assert response.json()["parties"] == [
        {"id": str(artist_party.id), "display_name": "Writer"}
    ]
    staff = User.objects.create_user(
        email="rights-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get("/api/platform/rights/works/").status_code == 403
    _, denied = create_api_client_key(
        organization=organization,
        name="Denied",
        description="",
        scopes=["music.read"],
        created_by=owner,
    )
    assert (
        client.get(
            "/api/developer/rights/works/",
            HTTP_AUTHORIZATION=f"Bearer {denied.secret}",
        ).status_code
        == 403
    )
    _, allowed = create_api_client_key(
        organization=organization,
        name="Rights",
        description="",
        scopes=["rights.read"],
        created_by=owner,
    )
    response = client.get(
        "/api/developer/rights/works/",
        HTTP_AUTHORIZATION=f"Bearer {allowed.secret}",
    )
    assert response.status_code == 200
    assert "royalties" not in str(response.json()).lower()


def test_postgresql_concurrent_master_and_publishing_splits(foundation):
    organization, owner, _, _, _, track = foundation
    work = create_work(
        actor=owner, organization=organization, data={"title": "Concurrent"}
    )
    parties = [party(owner, organization, name=f"Party {index}") for index in range(4)]

    def race(kind, first, second):
        barrier = Barrier(2)
        outcomes = []

        def attempt(party_id):
            close_old_connections()
            try:
                barrier.wait()
                actor = User.objects.get(pk=owner.pk)
                target_party = RightsParty.objects.get(pk=party_id)
                if kind == "master":
                    add_master_right(
                        actor=actor,
                        track=Track.objects.get(pk=track.pk),
                        data={
                            "party": target_party,
                            "ownership_percentage": Decimal("60"),
                        },
                    )
                else:
                    add_publishing_right(
                        actor=actor,
                        work=Work.objects.get(pk=work.pk),
                        data={
                            "party": target_party,
                            "right_type": "writer",
                            "ownership_percentage": Decimal("60"),
                        },
                    )
                outcomes.append("created")
            except ValidationError:
                outcomes.append("rejected")
            finally:
                close_old_connections()

        threads = [
            Thread(target=attempt, args=(value.id,)) for value in (first, second)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert outcomes.count("created") == 1
        assert outcomes.count("rejected") == 1

    race("master", parties[0], parties[1])
    race("publishing", parties[2], parties[3])


def test_postgresql_concurrent_generation_and_finalization(foundation):
    organization, owner, _, _, artist, track = foundation
    rights_party = party(owner, organization, artist)
    add_master_right(
        actor=owner,
        track=track,
        data={"party": rights_party, "ownership_percentage": Decimal("100")},
    )
    statement, line = statement_line(foundation)

    def run_concurrently(call):
        barrier = Barrier(2)
        outcomes = []

        def attempt():
            close_old_connections()
            try:
                barrier.wait()
                call(User.objects.get(pk=owner.pk))
                outcomes.append("ok")
            except ValidationError:
                outcomes.append("rejected")
            finally:
                close_old_connections()

        threads = [Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        return outcomes

    outcomes = run_concurrently(
        lambda actor: generate_allocations(
            actor=actor, line=type(line).objects.get(pk=line.pk)
        )
    )
    assert outcomes.count("ok") == 1 and outcomes.count("rejected") == 1
    outcomes = run_concurrently(
        lambda actor: finalize_statement(
            actor=actor, statement=RoyaltyStatement.objects.get(pk=statement.pk)
        )
    )
    assert outcomes.count("ok") == 1 and outcomes.count("rejected") == 1


def test_xlsx_rows_reads_first_worksheet_headers_and_values():
    workbook = BytesIO()
    with ZipFile(workbook, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Statement" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Track</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>Gross</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>Song One</t></is></c>'
            '<c r="B2"><v>125.50</v></c></row>'
            '</sheetData></worksheet>',
        )
    headers, rows = _xlsx_rows(BytesIO(workbook.getvalue()))
    assert headers == ["Track", "Gross"]
    assert rows == [{"Track": "Song One", "Gross": "125.50"}]
