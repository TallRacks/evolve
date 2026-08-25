from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier, Thread

import pytest
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections

from artists.models import Artist
from audit.models import AuditEvent
from bookings.models import Booking
from finance.admin import AllocationAdmin, InvoiceAdmin
from finance.models import Invoice, InvoiceLineItem, Payment, PaymentAllocation
from finance.services import (
    add_line_item,
    allocate_payment,
    create_invoice_from_booking,
    issue_invoice,
    record_payment,
    update_invoice,
    void_invoice,
    void_payment,
)
from notifications.models import Notification
from organizations.models import Membership, Organization
from promoters.models import Promoter
from users.models import User
from white_label.services import create_api_client_key

pytestmark = pytest.mark.django_db(transaction=True)
PASSWORD = "Test-only-finance-credential-123"


def membership(organization, role, email):
    user = User.objects.create_user(email=email, password=PASSWORD)
    Membership.objects.create(organization=organization, user=user, role=role)
    return user


@pytest.fixture
def foundation():
    organization = Organization.objects.create(name="Finance Org", slug="finance-org")
    owner = membership(organization, Membership.Role.OWNER, "finance-owner@example.invalid")
    manager = membership(organization, Membership.Role.MANAGER, "finance-manager@example.invalid")
    artist = Artist.objects.create(
        organization=organization, stage_name="Ledger Artist", slug="ledger-artist"
    )
    promoter = Promoter.objects.create(
        organization=organization, name="Ledger Promoter", slug="ledger-promoter"
    )
    booking = Booking.objects.create(
        organization=organization,
        artist=artist,
        promoter=promoter,
        title="Ledger Live",
        event_date=date.today() + timedelta(days=30),
        promoter_name_snapshot=promoter.name,
        currency="ZAR",
        performance_fee=Decimal("100.00"),
        balance_due_date=date.today() + timedelta(days=14),
        created_by=owner,
    )
    return organization, owner, manager, booking


def invoice_and_payment(foundation, payment_amount="100.00"):
    organization, owner, _, booking = foundation
    invoice = create_invoice_from_booking(actor=owner, booking=booking)
    invoice = issue_invoice(actor=owner, invoice=invoice)
    payment = record_payment(
        actor=owner,
        organization=organization,
        data={
            "currency": "ZAR",
            "amount": Decimal(payment_amount),
            "payment_date": date.today(),
            "method": Payment.Method.BANK_TRANSFER,
        },
    )
    return invoice, payment


def test_invoice_snapshot_totals_lifecycle_immutability_and_audit(foundation):
    organization, owner, _, booking = foundation
    invoice = create_invoice_from_booking(actor=owner, booking=booking)
    assert invoice.id and invoice.invoice_number.startswith("INV-")
    assert invoice.artist_name_snapshot == "Ledger Artist"
    assert invoice.billed_to_name == "Ledger Promoter"
    assert invoice.currency == "ZAR"
    assert invoice.total_amount == Decimal("100.00")
    booking.performance_fee = Decimal("200.00")
    booking.save()
    assert invoice.total_amount == Decimal("100.00")
    update_invoice(actor=owner, invoice=invoice, data={"tax_amount": Decimal("15.00")})
    invoice.refresh_from_db()
    assert invoice.total_amount == Decimal("115.00")
    invoice = issue_invoice(actor=owner, invoice=invoice)
    assert invoice.status == Invoice.Status.ISSUED and invoice.financial_state == "unpaid"
    stale_item = invoice.line_items.first()
    stale_item.description = "Changed after issue"
    with pytest.raises(ValidationError):
        stale_item.save()
    invoice.status = Invoice.Status.DRAFT
    with pytest.raises(ValidationError):
        invoice.save()
    with pytest.raises(ValidationError):
        update_invoice(actor=owner, invoice=invoice, data={"tax_amount": Decimal("2")})
    with pytest.raises(ValidationError):
        add_line_item(
            actor=owner,
            invoice=invoice,
            data={"description": "Late", "quantity": 1, "unit_amount": 1},
        )
    with pytest.raises(ValidationError):
        invoice.delete()
    assert AuditEvent.objects.filter(
        organization=organization, action="finance.invoice_issued"
    ).exists()


def test_line_item_validation_and_draft_removal(foundation):
    _, owner, _, booking = foundation
    invoice = create_invoice_from_booking(actor=owner, booking=booking)
    item = add_line_item(
        actor=owner,
        invoice=invoice,
        data={
            "description": "Travel",
            "quantity": Decimal("1.5"),
            "unit_amount": Decimal("20"),
            "sequence": 2,
        },
    )
    assert item.line_total == Decimal("30.00")
    with pytest.raises(ValidationError):
        InvoiceLineItem(invoice=invoice, description="Credit", quantity=1, unit_amount=-1).save()
    item.delete()
    assert not InvoiceLineItem.objects.filter(pk=item.pk).exists()


def test_payment_allocation_states_currency_limits_void_and_notifications(foundation):
    invoice, payment = invoice_and_payment(foundation)
    owner = foundation[1]
    first = allocate_payment(actor=owner, payment=payment, invoice=invoice, amount=Decimal("40.00"))
    invoice.refresh_from_db()
    assert first.id and invoice.financial_state == "partially_paid"
    allocate_payment(actor=owner, payment=payment, invoice=invoice, amount=Decimal("60.00"))
    invoice.refresh_from_db()
    assert invoice.financial_state == "paid" and invoice.balance_due == 0
    with pytest.raises(ValidationError):
        allocate_payment(actor=owner, payment=payment, invoice=invoice, amount=1)
    with pytest.raises(ValidationError):
        void_invoice(actor=owner, invoice=invoice, reason="No")
    with pytest.raises(ValidationError):
        void_payment(actor=owner, payment=payment, reason="No")
    assert not any(
        character.isdigit()
        for message in Notification.objects.filter(notification_type="invoice.paid").values_list(
            "message", flat=True
        )
        for character in message.replace(invoice.invoice_number, "")
    )


def test_payment_void_and_cross_org_currency_rejections(foundation):
    organization, owner, _, booking = foundation
    invoice = issue_invoice(
        actor=owner, invoice=create_invoice_from_booking(actor=owner, booking=booking)
    )
    payment = record_payment(
        actor=owner,
        organization=organization,
        data={
            "currency": "USD",
            "amount": 10,
            "payment_date": date.today(),
            "method": Payment.Method.CARD_EXTERNAL,
        },
    )
    assert not hasattr(payment, "card_number") and not hasattr(payment, "bank_account")
    with pytest.raises(ValidationError):
        allocate_payment(actor=owner, payment=payment, invoice=invoice, amount=1)
    payment = void_payment(actor=owner, payment=payment, reason="Duplicate")
    assert payment.status == Payment.Status.VOID
    with pytest.raises(ValidationError):
        payment.delete()

    voidable = create_invoice_from_booking(actor=owner, booking=booking)
    voidable.due_date = date.today() - timedelta(days=1)
    voidable.save()
    voidable = issue_invoice(actor=owner, invoice=voidable)
    assert voidable.financial_state == "overdue"
    voidable = void_invoice(actor=owner, invoice=voidable, reason="Cancelled event")
    assert voidable.status == Invoice.Status.VOID


def test_permissions_api_privacy_and_staff_no_bypass(client, foundation):
    organization, owner, manager, booking = foundation
    invoice = create_invoice_from_booking(actor=owner, booking=booking)
    with pytest.raises(PermissionDenied):
        create_invoice_from_booking(actor=manager, booking=booking)
    client.force_login(manager)
    assert (
        client.get(f"/api/finance/invoices/?organization_id={organization.id}").status_code == 403
    )
    assert (
        client.get(f"/api/finance/overview/?organization_id={organization.id}").status_code == 403
    )
    staff = User.objects.create_user(
        email="finance-staff@example.invalid", password=PASSWORD, is_staff=True
    )
    client.force_login(staff)
    assert client.get("/api/platform/finance/invoices/").status_code == 403
    root = User.objects.create_superuser(email="finance-root@example.invalid", password=PASSWORD)
    client.force_login(root)
    response = client.get(f"/api/finance/invoices/{invoice.id}/")
    assert response.status_code == 200 and response.json()["total_amount"] == "100.00"


def test_developer_finance_scope_and_curated_fields(client, foundation):
    organization, owner, _, booking = foundation
    create_invoice_from_booking(actor=owner, booking=booking)
    _, denied = create_api_client_key(
        organization=organization,
        name="No Finance",
        description="",
        scopes=["booking.read"],
        created_by=owner,
    )
    assert (
        client.get(
            "/api/developer/finance/invoices/",
            HTTP_AUTHORIZATION=f"Bearer {denied.secret}",
        ).status_code
        == 403
    )
    _, allowed = create_api_client_key(
        organization=organization,
        name="Finance",
        description="",
        scopes=["finance.read"],
        created_by=owner,
    )
    response = client.get(
        "/api/developer/finance/invoices/",
        HTTP_AUTHORIZATION=f"Bearer {allowed.secret}",
    )
    assert response.status_code == 200
    assert not (
        {"billed_to_address", "internal_notes", "billed_to_email"} & response.json()[0].keys()
    )


def test_postgresql_concurrent_allocation_cannot_overallocate(foundation):
    invoice, payment = invoice_and_payment(foundation)
    owner = foundation[1]
    barrier = Barrier(2)
    outcomes = []

    def attempt():
        close_old_connections()
        try:
            barrier.wait()
            allocate_payment(
                actor=User.objects.get(pk=owner.pk),
                payment=Payment.objects.get(pk=payment.pk),
                invoice=Invoice.objects.get(pk=invoice.pk),
                amount=Decimal("80.00"),
            )
            outcomes.append("allocated")
        except ValidationError:
            outcomes.append("rejected")
        finally:
            close_old_connections()

    threads = [Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert outcomes.count("allocated") == 1 and outcomes.count("rejected") == 1
    assert PaymentAllocation.objects.filter(payment=payment).aggregate(
        total=__import__("django").db.models.Sum("amount")
    )["total"] == Decimal("80.00")


def test_postgresql_concurrent_reference_generation(foundation):
    organization, owner, _, booking = foundation
    barrier = Barrier(4)
    references = []

    def create_record(kind):
        close_old_connections()
        try:
            barrier.wait()
            actor = User.objects.get(pk=owner.pk)
            if kind == "invoice":
                record = create_invoice_from_booking(
                    actor=actor, booking=Booking.objects.get(pk=booking.pk)
                )
                references.append(record.invoice_number)
            else:
                record = record_payment(
                    actor=actor,
                    organization=Organization.objects.get(pk=organization.pk),
                    data={
                        "currency": "ZAR",
                        "amount": 1,
                        "payment_date": date.today(),
                        "method": Payment.Method.OTHER,
                    },
                )
                references.append(record.payment_reference)
        finally:
            close_old_connections()

    kinds = ("invoice", "invoice", "payment", "payment")
    threads = [Thread(target=create_record, args=(kind,)) for kind in kinds]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(references) == 4
    assert len(set(references)) == 4


def test_admin_is_read_only_and_allocation_delete_blocked(foundation):
    invoice, payment = invoice_and_payment(foundation)
    request = type("Request", (), {"user": foundation[1]})()
    assert not InvoiceAdmin(Invoice, admin.site).has_change_permission(request, invoice)
    assert not AllocationAdmin(PaymentAllocation, admin.site).has_add_permission(request)
    allocation = allocate_payment(actor=foundation[1], payment=payment, invoice=invoice, amount=1)
    with pytest.raises(ValidationError):
        allocation.delete()
