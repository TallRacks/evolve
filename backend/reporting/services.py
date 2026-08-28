import csv
import io
from collections import Counter, defaultdict
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from artists.models import Artist
from bookings.models import Booking
from campaigns.models import Campaign
from contracts.models import Contract
from finance.models import Invoice, Payment
from music.models import Release
from production.models import ProductionAdvance
from promoters.models import Promoter
from rights.models import RoyaltyStatement, Work
from tasks.models import Task
from travel.models import TravelItinerary
from venues.models import Venue

REPORTS = {
    "bookings": ("Booking Pipeline", "booking.view"),
    "artists": ("Artist Activity", "artist.view"),
    "promoters": ("Promoters", "promoter.view"),
    "venues": ("Venues", "venue.view"),
    "production": ("Production Attention", "production.view"),
    "travel": ("Travel", "travel.view"),
    "tasks": ("Tasks / Workload", "task.view"),
    "finance": ("Finance", "finance.view"),
    "contracts": ("Contracts", "contract.view"),
    "music": ("Music / Releases", "music.view"),
    "campaigns": ("Campaigns / Rollouts", "campaign.view"),
    "rights": ("Rights Completeness", "rights.view"),
    "royalties": ("Royalty Statement Operations", "royalties.view"),
}


def _apply_filters(queryset, filters, allowed):
    for key, lookup in allowed.items():
        value = filters.get(key)
        if value not in (None, ""):
            queryset = queryset.filter(**{lookup: value})
    return queryset


def _summary(rows, key="status"):
    counts = Counter(str(row.get(key) or "unspecified") for row in rows)
    return {"total": len(rows), "by_status": dict(sorted(counts.items()))}


def report_data(organization, report_key, filters):
    if report_key == "bookings":
        qs = _apply_filters(
            Booking.objects.filter(organization=organization),
            filters,
            {
                "status": "status",
                "priority": "priority",
                "artist": "artist_id",
                "promoter": "promoter_id",
                "venue": "venue_id",
            },
        )
        if filters.get("date_from"):
            qs = qs.filter(event_date__gte=filters["date_from"])
        if filters.get("date_to"):
            qs = qs.filter(event_date__lte=filters["date_to"])
        qs = qs.select_related("artist", "promoter", "venue")
        rows = [
            {
                "reference": x.reference,
                "title": x.title,
                "artist": x.artist.stage_name,
                "date": x.event_date.isoformat(),
                "status": x.status,
                "priority": x.priority,
                "promoter": x.promoter.name if x.promoter else x.promoter_name_snapshot,
                "venue": x.venue.name if x.venue else x.venue_name_snapshot,
            }
            for x in qs[:1000]
        ]
    elif report_key == "artists":
        qs = Artist.objects.filter(organization=organization).annotate(
            bookings_count=Count("bookings", distinct=True),
            releases_count=Count("music_releases", distinct=True),
            tasks_count=Count("tasks", distinct=True),
        )
        rows = [
            {
                "artist": x.stage_name,
                "status": x.status,
                "bookings": x.bookings_count,
                "releases": x.releases_count,
                "tasks": x.tasks_count,
            }
            for x in qs[:1000]
        ]
    elif report_key == "promoters":
        qs = Promoter.objects.filter(organization=organization).annotate(
            bookings_count=Count("bookings", distinct=True)
        )
        rows = [
            {"promoter": x.name, "status": x.status, "bookings": x.bookings_count}
            for x in qs[:1000]
        ]
    elif report_key == "venues":
        qs = Venue.objects.filter(organization=organization).annotate(
            bookings_count=Count("bookings", distinct=True)
        )
        rows = [
            {"venue": x.name, "city": x.city, "status": x.status, "bookings": x.bookings_count}
            for x in qs[:1000]
        ]
    elif report_key == "production":
        qs = _apply_filters(
            ProductionAdvance.objects.filter(organization=organization),
            filters,
            {"status": "status"},
        ).select_related("artist", "booking")
        rows = [
            {
                "production": x.production_title,
                "artist": x.artist.stage_name,
                "booking": x.booking.reference,
                "status": x.status,
                "event_date": x.booking.event_date.isoformat(),
            }
            for x in qs[:1000]
        ]
    elif report_key == "travel":
        qs = _apply_filters(
            TravelItinerary.objects.filter(organization=organization), filters, {"status": "status"}
        ).select_related("artist", "booking")
        rows = [
            {
                "itinerary": x.title,
                "artist": x.artist.stage_name,
                "booking": x.booking.reference if x.booking else "",
                "status": x.status,
            }
            for x in qs[:1000]
        ]
    elif report_key == "tasks":
        qs = _apply_filters(
            Task.objects.filter(organization=organization, archived_at__isnull=True),
            filters,
            {
                "status": "status",
                "priority": "priority",
                "assignee": "assigned_membership_id",
                "artist": "artist_id",
            },
        ).select_related("assigned_membership__user")
        rows = [
            {
                "task": x.title,
                "assignee": x.assigned_membership.user.email
                if x.assigned_membership
                else "Unassigned",
                "status": x.status,
                "priority": x.priority,
                "due_at": x.due_at.isoformat() if x.due_at else "",
                "overdue": x.is_overdue,
            }
            for x in qs[:1000]
        ]
    elif report_key == "contracts":
        qs = _apply_filters(
            Contract.objects.filter(organization=organization), filters, {"status": "status"}
        )
        rows = [
            {
                "reference": x.reference,
                "title": x.title,
                "type": x.contract_type,
                "status": x.status,
                "expiry_date": x.expiry_date.isoformat() if x.expiry_date else "",
                "expired": x.is_expired,
            }
            for x in qs[:1000]
        ]
    elif report_key == "music":
        qs = _apply_filters(
            Release.objects.filter(organization=organization), filters, {"status": "status"}
        ).select_related("primary_artist")
        rows = [
            {
                "release": x.title,
                "artist": x.primary_artist.stage_name,
                "status": x.status,
                "release_date": x.release_date.isoformat() if x.release_date else "",
                "identifier_complete": bool(x.upc_ean),
            }
            for x in qs[:1000]
        ]
    elif report_key == "campaigns":
        qs = _apply_filters(
            Campaign.objects.filter(organization=organization), filters, {"status": "status"}
        ).select_related("artist")
        rows = [
            {"campaign": x.name, "artist": x.artist.stage_name, "status": x.status}
            for x in qs[:1000]
        ]
    elif report_key == "rights":
        qs = _apply_filters(
            Work.objects.filter(organization=organization), filters, {"status": "status"}
        ).annotate(
            track_count=Count("track_links", distinct=True),
            publishing_count=Count("publishing_rights", distinct=True),
        )
        rows = [
            {
                "work": x.title,
                "status": x.status,
                "iswc": x.iswc,
                "track_links": x.track_count,
                "publishing_rights": x.publishing_count,
                "complete": bool(x.iswc and x.track_count and x.publishing_count),
            }
            for x in qs[:1000]
        ]
    elif report_key == "royalties":
        qs = _apply_filters(
            RoyaltyStatement.objects.filter(organization=organization),
            filters,
            {"status": "status"},
        )
        rows = [
            {
                "reference": x.statement_reference,
                "status": x.status,
                "currency": x.currency,
                "period_start": x.period_start.isoformat(),
                "period_end": x.period_end.isoformat(),
            }
            for x in qs[:1000]
        ]
    elif report_key == "finance":
        currencies = defaultdict(
            lambda: {
                "invoices": defaultdict(lambda: Decimal("0")),
                "payments": defaultdict(lambda: Decimal("0")),
            }
        )
        rows = []
        for invoice in Invoice.objects.filter(organization=organization).prefetch_related(
            "line_items", "allocations__payment"
        ):
            total = (
                sum((line.line_total for line in invoice.line_items.all()), Decimal("0"))
                + invoice.tax_amount
            )
            paid = sum(
                (
                    allocation.amount
                    for allocation in invoice.allocations.all()
                    if allocation.payment.status == Payment.Status.RECORDED
                ),
                Decimal("0"),
            )
            if invoice.status in (Invoice.Status.VOID, Invoice.Status.CANCELLED):
                state = invoice.status
            elif invoice.status == Invoice.Status.DRAFT:
                state = "draft"
            elif total - paid <= 0:
                state = "paid"
            elif paid > 0:
                state = "partially_paid"
            elif invoice.due_date and invoice.due_date < timezone.localdate():
                state = "overdue"
            else:
                state = "unpaid"
            currencies[invoice.currency]["invoices"][state] += total
            rows.append(
                {
                    "record": invoice.invoice_number,
                    "kind": "invoice",
                    "status": state,
                    "currency": invoice.currency,
                    "amount": str(total),
                }
            )
        for payment in Payment.objects.filter(organization=organization).prefetch_related(
            "allocations"
        ):
            allocated = sum((item.amount for item in payment.allocations.all()), Decimal("0"))
            currencies[payment.currency]["payments"]["received"] += payment.amount
            currencies[payment.currency]["payments"]["allocated"] += allocated
            currencies[payment.currency]["payments"]["unallocated"] += payment.amount - allocated
            rows.append(
                {
                    "record": payment.payment_reference,
                    "kind": "payment",
                    "status": payment.status,
                    "currency": payment.currency,
                    "amount": str(payment.amount),
                }
            )
        currency_summary = {
            code: {
                group: {key: str(value) for key, value in values.items()}
                for group, values in groups.items()
            }
            for code, groups in currencies.items()
        }
        return {
            "report_key": report_key,
            "title": REPORTS[report_key][0],
            "summary": {"total": len(rows), "currencies": currency_summary},
            "rows": rows,
        }
    else:
        raise ValueError("Unknown report")
    return {
        "report_key": report_key,
        "title": REPORTS[report_key][0],
        "summary": _summary(rows),
        "rows": rows,
    }


def safe_csv(report):
    output = io.StringIO()
    rows = report["rows"]
    if not rows:
        return ""
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _safe_cell(value) for key, value in row.items()})
    return output.getvalue()


def _safe_cell(value):
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text
