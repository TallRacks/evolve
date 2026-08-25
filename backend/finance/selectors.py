from decimal import Decimal

from django.utils import timezone

from organizations.permissions import user_has_organization_permission

from .models import Invoice, Payment


def invoices_for_user(user):
    if user.is_active and user.is_superuser:
        return Invoice.objects.all()
    organization_ids = [
        m.organization_id
        for m in user.memberships.active()
        if user_has_organization_permission(user, m.organization, "finance.view")
    ]
    return Invoice.objects.filter(organization_id__in=organization_ids)


def payments_for_user(user):
    if user.is_active and user.is_superuser:
        return Payment.objects.all()
    organization_ids = [
        m.organization_id
        for m in user.memberships.active()
        if user_has_organization_permission(user, m.organization, "finance.view")
    ]
    return Payment.objects.filter(organization_id__in=organization_ids)


def overview(organization):
    invoices = Invoice.objects.filter(organization=organization).prefetch_related(
        "line_items", "allocations__payment"
    )
    currencies = {}
    for invoice in invoices:
        bucket = currencies.setdefault(
            invoice.currency,
            {
                "outstanding": Decimal("0.00"),
                "paid": Decimal("0.00"),
                "outstanding_count": 0,
                "overdue_count": 0,
                "paid_count": 0,
            },
        )
        if invoice.financial_state == "paid":
            bucket["paid"] += invoice.total_amount
            bucket["paid_count"] += 1
        elif invoice.status == Invoice.Status.ISSUED:
            bucket["outstanding"] += invoice.balance_due
            bucket["outstanding_count"] += 1
            if invoice.due_date and invoice.due_date < timezone.localdate():
                bucket["overdue_count"] += 1
    return currencies
