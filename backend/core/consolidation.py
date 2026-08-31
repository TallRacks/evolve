from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from artists.models import Artist
from bookings.models import Booking
from campaigns.models import Campaign, RolloutTask
from contacts.models import Contact
from contracts.models import Contract
from documents.models import Document
from documents.selectors import documents_for_user
from finance.models import Invoice
from integrations.models import EmailConnector, StorageProvider
from music.models import Release, Track
from notifications.models import NotificationRecipient
from organizations.models import Invitation, Organization
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from production.models import (
    AdvanceChecklistItem,
    AdvanceRequirement,
    ProductionAdvance,
)
from promoters.models import Promoter
from rights.models import Work
from tasks.models import Task
from travel.models import TravelItinerary
from users.models import User
from venues.models import Venue

RESULT_LIMIT = 6


def permitted_organizations(user, permission, organization_id=None):
    organizations = organizations_for_user(user)
    if organization_id:
        organizations = organizations.filter(pk=organization_id)
    return [org for org in organizations if user_has_organization_permission(user, org, permission)]


def result(obj, kind, title, subtitle, destination, status=None):
    value = {
        "id": str(obj.pk),
        "type": kind,
        "title": title,
        "subtitle": subtitle,
        "destination": destination,
    }
    if status:
        value["status"] = status
    return value


def global_search(user, query, organization_id=None):
    if not user.is_authenticated or not user.is_active:
        return []
    groups = []

    def add(kind, label, rows):
        rows = list(rows)
        if rows:
            groups.append(
                {
                    "type": kind,
                    "label": label,
                    "results": rows[:RESULT_LIMIT],
                    "has_more": len(rows) > RESULT_LIMIT,
                }
            )

    artist_orgs = permitted_organizations(user, "artist.view", organization_id)
    if artist_orgs:
        rows = (
            Artist.objects.filter(organization__in=artist_orgs)
            .filter(Q(stage_name__icontains=query) | Q(slug__icontains=query))
            .select_related("organization")
        )
        add(
            "artist",
            "Artists",
            (
                result(
                    x,
                    "artist",
                    x.stage_name,
                    x.organization.name,
                    f"/workspace/artists/{x.id}",
                    x.status,
                )
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )

    booking_orgs = permitted_organizations(user, "booking.view", organization_id)
    if booking_orgs:
        rows = (
            Booking.objects.filter(organization__in=booking_orgs)
            .filter(
                Q(reference__icontains=query)
                | Q(title__icontains=query)
                | Q(artist__stage_name__icontains=query)
                | Q(venue__name__icontains=query)
                | Q(promoter__name__icontains=query)
            )
            .select_related("artist", "venue", "promoter")
        )
        add(
            "booking",
            "Bookings",
            (
                result(
                    x,
                    "booking",
                    x.reference,
                    f"{x.artist.stage_name} / "
                    f"{x.venue.name if x.venue else x.venue_name_snapshot or 'Venue TBC'}",
                    f"/workspace/bookings/{x.id}",
                    x.status,
                )
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )

    directory = (
        (
            Promoter,
            "promoter",
            "Promoters",
            "promoter.view",
            "name",
            "/workspace/promoters/",
        ),
        (Venue, "venue", "Venues", "venue.view", "name", "/workspace/venues/"),
    )
    for model, kind, label, permission, field, destination in directory:
        orgs = permitted_organizations(user, permission, organization_id)
        if orgs:
            filters = Q(**{f"{field}__icontains": query})
            if model is Venue:
                filters |= Q(city__icontains=query)
            rows = model.objects.filter(organization__in=orgs).filter(filters)
            add(
                kind,
                label,
                (
                    result(
                        x,
                        kind,
                        x.name,
                        getattr(x, "city", ""),
                        destination + str(x.id),
                        x.status,
                    )
                    for x in rows[: RESULT_LIMIT + 1]
                ),
            )

    contact_orgs = permitted_organizations(user, "contact.view", organization_id)
    if contact_orgs:
        rows = (
            Contact.objects.filter(organization__in=contact_orgs)
            .filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
            )
            .order_by("last_name", "first_name")
        )
        add(
            "contact",
            "Contacts",
            (
                result(x, "contact", x.full_name, x.email, f"/workspace/contacts/{x.id}")
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )

    music_orgs = permitted_organizations(user, "music.view", organization_id)
    if music_orgs:
        releases = (
            Release.objects.filter(organization__in=music_orgs)
            .filter(Q(title__icontains=query) | Q(upc_ean__icontains=query))
            .select_related("primary_artist")
        )
        tracks = (
            Track.objects.filter(organization__in=music_orgs)
            .filter(Q(title__icontains=query) | Q(isrc__icontains=query))
            .select_related("primary_artist")
        )
        add(
            "release",
            "Releases",
            (
                result(
                    x,
                    "release",
                    x.title,
                    x.primary_artist.stage_name,
                    f"/workspace/music/releases/{x.id}",
                    x.status,
                )
                for x in releases[: RESULT_LIMIT + 1]
            ),
        )
        add(
            "track",
            "Tracks",
            (
                result(
                    x,
                    "track",
                    x.title,
                    x.primary_artist.stage_name,
                    f"/workspace/music/tracks/{x.id}",
                    x.status,
                )
                for x in tracks[: RESULT_LIMIT + 1]
            ),
        )

    campaign_orgs = permitted_organizations(user, "campaign.view", organization_id)
    if campaign_orgs:
        rows = Campaign.objects.filter(
            organization__in=campaign_orgs, name__icontains=query
        ).select_related("artist")
        add(
            "campaign",
            "Campaigns",
            (
                result(
                    x,
                    "campaign",
                    x.name,
                    x.artist.stage_name,
                    f"/workspace/campaigns/{x.id}",
                    x.status,
                )
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )

    rights_orgs = permitted_organizations(user, "rights.view", organization_id)
    if rights_orgs:
        rows = Work.objects.filter(organization__in=rights_orgs).filter(
            Q(title__icontains=query) | Q(iswc__icontains=query)
        )
        add(
            "work",
            "Works",
            (
                result(
                    x,
                    "work",
                    x.title,
                    x.iswc or "No ISWC",
                    f"/workspace/rights/works/{x.id}",
                    x.status,
                )
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )

    travel_orgs = permitted_organizations(user, "travel.view", organization_id)
    if travel_orgs:
        rows = (
            TravelItinerary.objects.filter(organization__in=travel_orgs)
            .filter(
                Q(title__icontains=query)
                | Q(artist__stage_name__icontains=query)
                | Q(booking__reference__icontains=query)
                | Q(segments__provider__icontains=query)
                | Q(segments__flight_number__icontains=query)
            )
            .select_related("artist", "booking")
            .distinct()
        )
        add(
            "travel",
            "Travel",
            (
                result(
                    x,
                    "travel",
                    x.title,
                    f"{x.artist.stage_name} / {x.booking.reference if x.booking else 'No booking'}",
                    f"/workspace/travel/{x.id}",
                    x.status,
                )
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )

    production_orgs = permitted_organizations(user, "production.view", organization_id)
    if production_orgs:
        rows = (
            ProductionAdvance.objects.filter(organization__in=production_orgs)
            .filter(
                Q(production_title__icontains=query)
                | Q(artist__stage_name__icontains=query)
                | Q(booking__reference__icontains=query)
                | Q(venue__name__icontains=query)
                | Q(promoter__name__icontains=query)
            )
            .select_related("artist", "booking", "venue", "promoter")
            .distinct()
        )
        add(
            "production",
            "Production",
            (
                result(
                    x,
                    "production",
                    x.production_title,
                    f"{x.artist.stage_name} / {x.booking.reference}",
                    f"/workspace/production/{x.id}",
                    x.status,
                )
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )

    contract_orgs = permitted_organizations(user, "contract.view", organization_id)
    if contract_orgs:
        rows = (
            Contract.objects.filter(organization__in=contract_orgs)
            .filter(
                Q(reference__icontains=query)
                | Q(title__icontains=query)
                | Q(artist__stage_name__icontains=query)
                | Q(booking__reference__icontains=query)
                | Q(promoter__name__icontains=query)
            )
            .select_related("artist", "booking", "promoter")
            .distinct()
        )
        add(
            "contract",
            "Contracts",
            (
                result(
                    row,
                    "contract",
                    f"{row.reference} / {row.title}",
                    (
                        f"{row.get_contract_type_display()} / "
                        f"{row.artist.stage_name if row.artist else 'No Artist'}"
                    ),
                    f"/workspace/contracts/{row.id}",
                    row.status,
                )
                for row in rows[: RESULT_LIMIT + 1]
            ),
        )

    document_orgs = permitted_organizations(user, "document.view", organization_id)
    if document_orgs:
        document_ids = []
        for org in document_orgs:
            document_ids.extend(
                documents_for_user(user, org)
                .filter(title__icontains=query)
                .values_list("pk", flat=True)[: RESULT_LIMIT + 1]
            )
        rows = Document.objects.filter(pk__in=document_ids).order_by("-updated_at")
        add(
            "document",
            "Documents",
            (
                result(
                    x,
                    "document",
                    x.title,
                    x.get_document_type_display(),
                    f"/workspace/documents/{x.id}",
                    x.status,
                )
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )

    finance_orgs = permitted_organizations(user, "finance.view", organization_id)
    if finance_orgs:
        rows = Invoice.objects.filter(
            organization__in=finance_orgs, invoice_number__icontains=query
        )
        add(
            "invoice",
            "Invoices",
            (
                result(
                    x,
                    "invoice",
                    x.invoice_number,
                    x.currency,
                    f"/workspace/finance/invoices/{x.id}",
                    x.status,
                )
                for x in rows[: RESULT_LIMIT + 1]
            ),
        )
    return groups


def dashboard(user, organization_id=None):
    if user.is_superuser and not organization_id:
        return {
            "mode": "platform",
            "counts": {
                "organizations": Organization.objects.count(),
                "artists": Artist.objects.count(),
                "bookings": Booking.objects.count(),
                "active_users": User.objects.filter(is_active=True).count(),
                "production_activity": ProductionAdvance.objects.exclude(
                    status__in=("completed", "cancelled", "archived")
                ).count(),
            },
            "configuration": {
                "email": EmailConnector.objects.filter(is_active=True, is_default=True)
                .values_list("connection_status", flat=True)
                .first()
                or "not_configured",
                "storage": StorageProvider.objects.filter(is_active=True, is_default=True)
                .values_list("connection_status", flat=True)
                .first()
                or "not_configured",
            },
            "upcoming_bookings": [],
            "attention": [],
            "today": [],
        }

    organizations = permitted_organizations(user, "organization.view", organization_id)
    if len(organizations) != 1:
        return {
            "mode": "workspace",
            "counts": {},
            "upcoming_bookings": [],
            "attention": [],
            "today": [],
        }

    organization = organizations[0]
    now = timezone.now()
    today = timezone.localdate()
    week = today + timedelta(days=7)
    counts = {}
    attention = []
    today_items = []

    def add_attention(severity, domain, title, reason, destination, due=None, owner=None):
        item = {
            "severity": severity,
            "domain": domain,
            "title": title,
            "reason": reason,
            "destination": destination,
        }
        if due:
            item["due"] = due
        if owner:
            item["owner"] = owner
        attention.append(item)

    if user_has_organization_permission(user, organization, "artist.view"):
        counts["active_artists"] = Artist.objects.filter(
            organization=organization, status=Artist.Status.ACTIVE
        ).count()

    upcoming = []
    if user_has_organization_permission(user, organization, "booking.view"):
        booking_qs = (
            Booking.objects.filter(organization=organization, event_date__gte=today)
            .exclude(status__in=(Booking.Status.CANCELLED, Booking.Status.DECLINED))
            .select_related("artist", "venue")
        )
        counts["upcoming_bookings"] = booking_qs.count()
        upcoming = [
            {
                "id": str(booking.id),
                "reference": booking.reference,
                "artist": booking.artist.stage_name,
                "date": booking.event_date,
                "days_out": (booking.event_date - today).days,
                "venue": booking.venue.name if booking.venue else booking.venue_name_snapshot,
                "status": booking.status,
                "priority": booking.priority,
            }
            for booking in booking_qs.order_by("event_date")[:6]
        ]
        for booking in booking_qs.filter(event_date=today)[:5]:
            today_items.append(
                {
                    "domain": "Booking",
                    "title": f"{booking.artist.stage_name} - {booking.title}",
                    "destination": f"/workspace/bookings/{booking.id}",
                    "time": booking.event_start_datetime,
                }
            )
        actionable_bookings = booking_qs.filter(event_date__lte=week).order_by(
            "event_date", "priority"
        )
        for booking in actionable_bookings.filter(priority__in=("urgent", "high"))[:4]:
            add_attention(
                "critical" if booking.priority == "urgent" else "high",
                "Bookings",
                booking.reference,
                f"{booking.get_priority_display()} booking is "
                f"{(booking.event_date - today).days} days out.",
                f"/workspace/bookings/{booking.id}",
                booking.event_date,
            )
        for booking in actionable_bookings.filter(call_sheet__isnull=True)[:4]:
            add_attention(
                "high",
                "Call Sheets",
                booking.reference,
                "Upcoming booking has no Call Sheet.",
                f"/workspace/bookings/{booking.id}",
                booking.event_date,
            )

    if user_has_organization_permission(user, organization, "task.view"):
        open_tasks = Task.objects.filter(organization=organization).exclude(
            status__in=(Task.Status.DONE, Task.Status.CANCELLED)
        )
        counts["open_tasks"] = open_tasks.count()
        for task in open_tasks.filter(due_at__lt=now).select_related("assigned_membership__user")[
            :5
        ]:
            owner = None
            if task.assigned_membership:
                owner = (
                    task.assigned_membership.user.get_full_name()
                    or task.assigned_membership.user.email
                )
            add_attention(
                "critical" if task.priority == Task.Priority.URGENT else "high",
                "Tasks",
                task.title,
                "Task is overdue.",
                f"/workspace/tasks/{task.id}",
                task.due_at,
                owner,
            )
        for task in open_tasks.filter(due_at__date=today)[:5]:
            today_items.append(
                {
                    "domain": "Task",
                    "title": task.title,
                    "destination": f"/workspace/tasks/{task.id}",
                    "time": task.due_at,
                }
            )

    if user_has_organization_permission(user, organization, "production.view"):
        active_advances = ProductionAdvance.objects.filter(organization=organization).exclude(
            status__in=("completed", "cancelled", "archived")
        )
        counts["production_due_soon"] = active_advances.filter(
            advance_due_at__gte=now, advance_due_at__lte=now + timedelta(days=7)
        ).count()
        counts["overdue_production"] = active_advances.filter(advance_due_at__lt=now).count()
        blocked = AdvanceRequirement.objects.filter(
            advance__organization=organization,
            is_active=True,
            status="blocked",
            priority="critical",
        ).select_related("advance")
        counts["blocked_critical_requirements"] = blocked.count()
        counts["overdue_production_checklist"] = AdvanceChecklistItem.objects.filter(
            advance__organization=organization,
            is_active=True,
            is_completed=False,
            due_at__lt=now,
        ).count()
        for requirement in blocked[:4]:
            add_attention(
                "critical",
                "Production",
                requirement.title,
                "Critical production requirement is blocked.",
                f"/workspace/production/{requirement.advance_id}",
            )

    if user_has_organization_permission(user, organization, "travel.view"):
        active_travel = TravelItinerary.objects.filter(organization=organization).exclude(
            status__in=(TravelItinerary.Status.CANCELLED, TravelItinerary.Status.ARCHIVED)
        )
        counts["upcoming_travel"] = active_travel.filter(
            status__in=(TravelItinerary.Status.CONFIRMED, TravelItinerary.Status.IN_PROGRESS)
        ).count()
        for itinerary in active_travel.filter(
            status=TravelItinerary.Status.DRAFT,
            starts_at__gte=now,
            starts_at__lte=now + timedelta(days=14),
        )[:4]:
            add_attention(
                "high",
                "Travel",
                itinerary.title,
                "Upcoming itinerary is not confirmed.",
                f"/workspace/travel/{itinerary.id}",
                itinerary.starts_at,
            )

    if user_has_organization_permission(user, organization, "contract.view"):
        contracts = Contract.objects.filter(organization=organization)
        counts["contracts_needing_review"] = contracts.filter(
            status=Contract.Status.IN_REVIEW
        ).count()
        counts["pending_contract_approvals"] = (
            contracts.filter(approvals__status="pending", approvals__membership__user=user)
            .distinct()
            .count()
        )
        for contract in contracts.filter(
            status__in=(Contract.Status.IN_REVIEW, Contract.Status.APPROVED, Contract.Status.SENT)
        )[:4]:
            add_attention(
                "high",
                "Contracts",
                contract.reference,
                f"Contract requires action: {contract.get_status_display()}.",
                f"/workspace/contracts/{contract.id}",
                contract.expiry_date,
            )

    if user_has_organization_permission(user, organization, "finance.view"):
        invoices = Invoice.objects.filter(organization=organization)
        counts["draft_invoices"] = invoices.filter(status=Invoice.Status.DRAFT).count()
        overdue_invoices = invoices.filter(
            status=Invoice.Status.ISSUED, due_date__lt=today
        ).order_by("due_date")
        counts["overdue_invoices"] = overdue_invoices.count()
        for invoice in overdue_invoices[:4]:
            add_attention(
                "critical",
                "Finance",
                invoice.invoice_number,
                "Issued invoice is past its due date.",
                f"/workspace/finance/invoices/{invoice.id}",
                invoice.due_date,
            )

    if user_has_organization_permission(user, organization, "music.view"):
        upcoming_releases = Release.objects.filter(
            organization=organization,
            planned_release_date__gte=today,
            planned_release_date__lte=today + timedelta(days=30),
        ).exclude(
            status__in=(Release.Status.RELEASED, Release.Status.CANCELLED, Release.Status.ARCHIVED)
        )
        counts["upcoming_releases"] = upcoming_releases.count()
        for release in upcoming_releases.filter(
            tasks__status__in=(Task.Status.TODO, Task.Status.BLOCKED)
        ).distinct()[:4]:
            add_attention(
                "high",
                "Music",
                release.title,
                "Upcoming release has incomplete deliverables.",
                f"/workspace/music/releases/{release.id}",
                release.planned_release_date,
            )

    if user_has_organization_permission(user, organization, "rollout.view"):
        overdue_rollout_tasks = RolloutTask.objects.filter(
            rollout__organization=organization,
            due_date__lt=today,
            status__in=(
                RolloutTask.Status.TODO,
                RolloutTask.Status.IN_PROGRESS,
                RolloutTask.Status.BLOCKED,
            ),
        ).select_related("rollout")
        for task in overdue_rollout_tasks[:4]:
            add_attention(
                "critical" if task.status == RolloutTask.Status.BLOCKED else "high",
                "Rollouts",
                task.title,
                "Rollout task is overdue.",
                f"/workspace/rollouts/{task.rollout_id}",
                task.due_date,
            )

    if user_has_organization_permission(user, organization, "rights.view"):
        incomplete_master = (
            Track.objects.filter(organization=organization, master_rights__isnull=False)
            .annotate(allocated=Sum("master_rights__ownership_percentage"))
            .filter(allocated__lt=100)
        )
        incomplete_publishing = (
            Work.objects.filter(organization=organization, publishing_rights__isnull=False)
            .annotate(allocated=Sum("publishing_rights__ownership_percentage"))
            .filter(allocated__lt=100)
        )
        counts["incomplete_master_splits"] = incomplete_master.count()
        counts["incomplete_publishing_splits"] = incomplete_publishing.count()
        for work in incomplete_publishing[:4]:
            add_attention(
                "high",
                "Rights",
                work.title,
                "Publishing ownership is incomplete.",
                f"/workspace/rights/works/{work.id}",
            )

    if user_has_organization_permission(user, organization, "membership.manage"):
        counts["pending_invitations"] = Invitation.objects.filter(
            organization=organization,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=now,
        ).count()

    counts["unread_notifications"] = NotificationRecipient.objects.filter(
        user=user,
        notification__organization=organization,
        read_at__isnull=True,
        archived_at__isnull=True,
    ).count()
    severity_rank = {"critical": 0, "high": 1, "normal": 2}
    visible_attention = sorted(
        attention, key=lambda item: (severity_rank[item["severity"]], str(item.get("due") or ""))
    )[:12]
    counts["needs_attention"] = len(attention)
    return {
        "mode": "workspace",
        "organization": {"id": str(organization.id), "name": organization.name},
        "counts": counts,
        "upcoming_bookings": upcoming,
        "attention": visible_attention,
        "today": sorted(today_items, key=lambda item: str(item.get("time") or ""))[:10],
    }
