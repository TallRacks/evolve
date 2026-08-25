from django.db.models import Q, Sum
from django.utils import timezone

from artists.models import Artist
from bookings.models import Booking
from campaigns.models import Campaign
from contacts.models import Contact
from documents.models import Document
from documents.selectors import documents_for_user
from finance.models import Invoice
from music.models import Release, Track
from notifications.models import NotificationRecipient
from organizations.models import Invitation, Organization
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from promoters.models import Promoter
from rights.models import Work
from travel.models import TravelItinerary, TravelSegment
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
            },
            "upcoming_bookings": [],
        }
    organizations = permitted_organizations(user, "organization.view", organization_id)
    if len(organizations) != 1:
        return {"mode": "workspace", "counts": {}, "upcoming_bookings": []}
    organization = organizations[0]
    today = timezone.localdate()
    counts = {}
    if user_has_organization_permission(user, organization, "artist.view"):
        counts["active_artists"] = Artist.objects.filter(
            organization=organization, status=Artist.Status.ACTIVE
        ).count()
    upcoming = []
    if user_has_organization_permission(user, organization, "booking.view"):
        bookings = (
            Booking.objects.filter(organization=organization, event_date__gte=today)
            .exclude(status__in=(Booking.Status.CANCELLED, Booking.Status.DECLINED))
            .select_related("artist", "venue")
            .order_by("event_date")[:6]
        )
        counts["upcoming_bookings"] = (
            Booking.objects.filter(organization=organization, event_date__gte=today)
            .exclude(status__in=(Booking.Status.CANCELLED, Booking.Status.DECLINED))
            .count()
        )
        upcoming = [
            {
                "id": str(x.id),
                "reference": x.reference,
                "artist": x.artist.stage_name,
                "date": x.event_date,
                "venue": x.venue.name if x.venue else x.venue_name_snapshot,
                "status": x.status,
            }
            for x in bookings
        ]
    if user_has_organization_permission(user, organization, "membership.manage"):
        counts["pending_invitations"] = Invitation.objects.filter(
            organization=organization,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).count()
    counts["unread_notifications"] = NotificationRecipient.objects.filter(
        user=user,
        notification__organization=organization,
        read_at__isnull=True,
        archived_at__isnull=True,
    ).count()
    if user_has_organization_permission(user, organization, "travel.view"):
        next_segment = (
            TravelSegment.objects.filter(
                itinerary__organization=organization,
                departure_at__gte=timezone.now(),
            )
            .exclude(status=TravelSegment.Status.CANCELLED)
            .select_related("itinerary__artist")
            .order_by("departure_at")
            .first()
        )
        counts["upcoming_travel"] = TravelItinerary.objects.filter(
            organization=organization,
            status__in=(TravelItinerary.Status.CONFIRMED, TravelItinerary.Status.IN_PROGRESS),
        ).count()
        if next_segment:
            counts["next_travel"] = {
                "itinerary_id": str(next_segment.itinerary_id),
                "artist": next_segment.itinerary.artist.stage_name,
                "departure_at": next_segment.departure_at,
                "destination": next_segment.arrival_location,
            }
    if user_has_organization_permission(user, organization, "finance.view"):
        counts["draft_invoices"] = Invoice.objects.filter(
            organization=organization, status=Invoice.Status.DRAFT
        ).count()
    if user_has_organization_permission(user, organization, "rights.view"):
        counts["incomplete_master_splits"] = (
            Track.objects.filter(organization=organization, master_rights__isnull=False)
            .annotate(allocated=Sum("master_rights__ownership_percentage"))
            .filter(allocated__lt=100)
            .count()
        )
        counts["incomplete_publishing_splits"] = (
            Work.objects.filter(organization=organization, publishing_rights__isnull=False)
            .annotate(allocated=Sum("publishing_rights__ownership_percentage"))
            .filter(allocated__lt=100)
            .count()
        )
    return {
        "mode": "workspace",
        "organization": {"id": str(organization.id), "name": organization.name},
        "counts": counts,
        "upcoming_bookings": upcoming,
    }
