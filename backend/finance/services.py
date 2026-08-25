from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from notifications.services import booking_team_users, create_notification
from organizations.models import Membership
from organizations.permissions import user_has_organization_permission

from .models import Invoice, InvoiceLineItem, Payment, PaymentAllocation


def require(actor, organization, permission):
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission to access financial records.")


def finance_users(organization):
    return [
        membership.user
        for membership in Membership.objects.active()
        .filter(
            organization=organization,
            role__in=(Membership.Role.OWNER, Membership.Role.ADMIN),
        )
        .select_related("user")
    ]


def emit(actor, organization, action, resource, description, request=None):
    return record_event(
        actor=actor,
        organization=organization,
        action=action,
        resource=resource,
        description=description,
        request=request,
    )


@transaction.atomic
def create_invoice(*, actor, organization, data, request=None):
    require(actor, organization, "finance.manage")
    booking = data.get("booking")
    if booking:
        require(actor, organization, "booking.commercial.view")
        if booking.organization_id != organization.id:
            raise ValidationError("Booking and invoice must belong to the same organization.")
    invoice = Invoice(organization=organization, created_by=actor, **data)
    invoice.full_clean()
    invoice.save()
    emit(
        actor,
        organization,
        "finance.invoice_created",
        invoice,
        f"Created invoice {invoice.invoice_number}.",
        request,
    )
    return invoice


@transaction.atomic
def create_invoice_from_booking(*, actor, booking, request=None):
    require(actor, booking.organization, "finance.manage")
    require(actor, booking.organization, "booking.commercial.view")
    if booking.performance_fee is None:
        raise ValidationError("Booking requires a performance fee before invoice creation.")
    invoice = create_invoice(
        actor=actor,
        organization=booking.organization,
        data={
            "booking": booking,
            "artist_name_snapshot": booking.artist.stage_name,
            "billed_to_name": booking.promoter_name_snapshot or booking.title,
            "currency": booking.currency,
            "due_date": booking.balance_due_date,
        },
        request=request,
    )
    add_line_item(
        actor=actor,
        invoice=invoice,
        data={
            "description": f"Performance fee - {booking.artist.stage_name} / {booking.title}",
            "quantity": Decimal("1"),
            "unit_amount": booking.performance_fee,
            "sequence": 1,
            "category": "performance_fee",
        },
        request=request,
    )
    return invoice


@transaction.atomic
def update_invoice(*, actor, invoice, data, request=None):
    require(actor, invoice.organization, "finance.manage")
    locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if locked.status != Invoice.Status.DRAFT:
        raise ValidationError("Only draft invoices can be edited.")
    for field, value in data.items():
        setattr(locked, field, value)
    locked.full_clean()
    locked.save()
    emit(
        actor,
        locked.organization,
        "finance.invoice_updated",
        locked,
        f"Updated draft invoice {locked.invoice_number} fields: {', '.join(sorted(data))}.",
        request,
    )
    return locked


@transaction.atomic
def add_line_item(*, actor, invoice, data, request=None):
    require(actor, invoice.organization, "finance.manage")
    locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if locked.status != Invoice.Status.DRAFT:
        raise ValidationError("Line items are editable only while the invoice is draft.")
    item = InvoiceLineItem(invoice=locked, **data)
    item.save()
    emit(
        actor,
        locked.organization,
        "finance.line_item_added",
        item,
        f"Added line item to {locked.invoice_number}.",
        request,
    )
    return item


@transaction.atomic
def update_line_item(*, actor, item, data, request=None):
    require(actor, item.invoice.organization, "finance.manage")
    locked_invoice = Invoice.objects.select_for_update().get(pk=item.invoice_id)
    locked = InvoiceLineItem.objects.get(pk=item.pk)
    if locked_invoice.status != Invoice.Status.DRAFT:
        raise ValidationError("Line items are editable only while the invoice is draft.")
    for field, value in data.items():
        setattr(locked, field, value)
    locked.save()
    emit(
        actor,
        locked_invoice.organization,
        "finance.line_item_updated",
        locked,
        f"Updated line item on {locked_invoice.invoice_number}.",
        request,
    )
    return locked


@transaction.atomic
def remove_line_item(*, actor, item, request=None):
    require(actor, item.invoice.organization, "finance.manage")
    invoice = Invoice.objects.select_for_update().get(pk=item.invoice_id)
    if invoice.status != Invoice.Status.DRAFT:
        raise ValidationError("Line items are editable only while the invoice is draft.")
    emit(
        actor,
        invoice.organization,
        "finance.line_item_removed",
        item,
        f"Removed line item from {invoice.invoice_number}.",
        request,
    )
    item.delete()


@transaction.atomic
def issue_invoice(*, actor, invoice, request=None):
    require(actor, invoice.organization, "finance.invoice.issue")
    locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if locked.status != Invoice.Status.DRAFT or not locked.line_items.exists():
        raise ValidationError("Only a draft invoice with line items can be issued.")
    if not locked.billed_to_name or locked.total_amount <= 0:
        raise ValidationError("Invoice billing identity and a positive total are required.")
    now = timezone.now()
    Invoice.objects.filter(pk=locked.pk).update(
        status=Invoice.Status.ISSUED,
        issue_date=locked.issue_date or now.date(),
        issued_by=actor,
        issued_at=now,
        updated_at=now,
    )
    locked.refresh_from_db()
    emit(
        actor,
        locked.organization,
        "finance.invoice_issued",
        locked,
        f"Issued invoice {locked.invoice_number}.",
        request,
    )
    recipients = (
        booking_team_users(locked.booking) if locked.booking else finance_users(locked.organization)
    )
    create_notification(
        organization=locked.organization,
        notification_type="invoice.issued",
        category="finance",
        title="Invoice issued",
        message=f"Invoice {locked.invoice_number} was issued.",
        users=recipients,
        actor=actor,
        source=locked,
        action_url=f"/workspace/finance/invoices/{locked.pk}",
    )
    return locked


@transaction.atomic
def void_invoice(*, actor, invoice, reason, request=None):
    require(actor, invoice.organization, "finance.manage")
    locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if locked.status != Invoice.Status.ISSUED:
        raise ValidationError("Only issued invoices can be voided.")
    if locked.allocations.filter(payment__status=Payment.Status.RECORDED).exists():
        raise ValidationError("Invoices with active payment allocations cannot be voided.")
    now = timezone.now()
    Invoice.objects.filter(pk=locked.pk).update(
        status=Invoice.Status.VOID,
        voided_by=actor,
        voided_at=now,
        void_reason=reason,
        updated_at=now,
    )
    locked.refresh_from_db()
    emit(
        actor,
        locked.organization,
        "finance.invoice_voided",
        locked,
        f"Voided invoice {locked.invoice_number}; reason recorded.",
        request,
    )
    return locked


@transaction.atomic
def record_payment(*, actor, organization, data, request=None):
    require(actor, organization, "finance.payment.record")
    payment = Payment(organization=organization, recorded_by=actor, **data)
    payment.full_clean()
    payment.save()
    emit(
        actor,
        organization,
        "finance.payment_recorded",
        payment,
        f"Recorded payment {payment.payment_reference}.",
        request,
    )
    create_notification(
        organization=organization,
        notification_type="payment.recorded",
        category="finance",
        title="Payment recorded",
        message=f"Payment {payment.payment_reference} was recorded.",
        users=finance_users(organization),
        actor=actor,
        source=payment,
        action_url=f"/workspace/finance/payments/{payment.pk}",
    )
    return payment


@transaction.atomic
def allocate_payment(*, actor, payment, invoice, amount, request=None):
    require(actor, payment.organization, "finance.payment.allocate")
    locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)
    locked_invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if locked_payment.organization_id != locked_invoice.organization_id:
        raise ValidationError("Payment and invoice must belong to the same organization.")
    if locked_payment.currency != locked_invoice.currency:
        raise ValidationError("Payment and invoice currencies must match.")
    if (
        locked_payment.status != Payment.Status.RECORDED
        or locked_invoice.status != Invoice.Status.ISSUED
    ):
        raise ValidationError("Only active payments can be allocated to issued invoices.")
    amount = Decimal(amount)
    if (
        amount <= 0
        or amount > locked_payment.remaining_amount
        or amount > locked_invoice.balance_due
    ):
        raise ValidationError("Allocation exceeds the available payment or invoice balance.")
    was_paid = locked_invoice.balance_due <= 0
    allocation = PaymentAllocation.objects.create(
        payment=locked_payment, invoice=locked_invoice, amount=amount, created_by=actor
    )
    emit(
        actor,
        locked_payment.organization,
        "finance.payment_allocated",
        allocation,
        "Allocated payment "
        f"{locked_payment.payment_reference} to invoice {locked_invoice.invoice_number}.",
        request,
    )
    locked_invoice.refresh_from_db()
    if not was_paid and locked_invoice.balance_due <= 0:
        recipients = (
            booking_team_users(locked_invoice.booking)
            if locked_invoice.booking
            else finance_users(locked_invoice.organization)
        )
        create_notification(
            organization=locked_invoice.organization,
            notification_type="invoice.paid",
            category="finance",
            title="Invoice paid",
            message=f"Invoice {locked_invoice.invoice_number} was paid.",
            users=recipients,
            actor=actor,
            source=locked_invoice,
            action_url=f"/workspace/finance/invoices/{locked_invoice.pk}",
        )
    return allocation


@transaction.atomic
def void_payment(*, actor, payment, reason, request=None):
    require(actor, payment.organization, "finance.payment.record")
    locked = Payment.objects.select_for_update().get(pk=payment.pk)
    if locked.status != Payment.Status.RECORDED:
        raise ValidationError("Only recorded payments can be voided.")
    if locked.allocations.exists():
        raise ValidationError("Allocated payments cannot be voided.")
    now = timezone.now()
    Payment.objects.filter(pk=locked.pk).update(
        status=Payment.Status.VOID,
        voided_by=actor,
        voided_at=now,
        void_reason=reason,
        updated_at=now,
    )
    locked.refresh_from_db()
    emit(
        actor,
        locked.organization,
        "finance.payment_voided",
        locked,
        f"Voided payment {locked.payment_reference}; reason recorded.",
        request,
    )
    return locked
