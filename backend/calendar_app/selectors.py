from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from artists.selectors import portal_artists_for_user
from bookings.models import Booking
from callsheets.models import CallSheetVersion
from campaigns.models import Campaign, RolloutMilestone, RolloutTask
from music.models import Release

from .models import CalendarEvent

MAX_WINDOW_DAYS = 366


def _aware(value, tz_name=settings.TIME_ZONE):
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value, ZoneInfo(tz_name))
    return timezone.make_aware(datetime.combine(value, time.min), ZoneInfo(tz_name))


def _item(
    source_type,
    obj,
    title,
    start,
    end=None,
    artist=None,
    status="active",
    url="",
    priority=None,
    all_day=False,
):
    return {
        "id": f"{source_type}:{obj.pk}",
        "source_type": source_type,
        "source_id": str(obj.pk),
        "title": title,
        "starts_at": _aware(start).isoformat(),
        "ends_at": _aware(end).isoformat() if end else None,
        "all_day": all_day,
        "status": status,
        "artist": ({"id": str(artist.pk), "name": artist.stage_name} if artist else None),
        "organization": {"id": str(obj.organization_id)},
        "url": url,
        "category": source_type,
        "priority": priority,
    }


def visible_events(user, organization):
    qs = CalendarEvent.objects.filter(organization=organization).select_related(
        "artist", "owner_membership", "created_by"
    )
    if user and user.is_superuser:
        return qs
    if not user:
        return qs.filter(visibility=CalendarEvent.Visibility.ORGANIZATION)
    return qs.filter(
        ~Q(visibility=CalendarEvent.Visibility.PRIVATE)
        | Q(created_by=user)
        | Q(owner_membership__user=user)
    )


def get_calendar_items(user, organization, start, end, filters=None, portal=False):
    filters = filters or {}
    if end < start or end - start > timedelta(days=MAX_WINDOW_DAYS):
        raise ValueError("Calendar range must be ordered and no longer than 366 days.")
    artist_id = filters.get("artist")
    allowed_artist_ids = (
        list(
            portal_artists_for_user(user)
            .filter(organization=organization)
            .values_list("id", flat=True)
        )
        if portal
        else None
    )
    if portal and not allowed_artist_ids:
        return []

    def artist_filter(qs, field):
        if artist_id:
            qs = qs.filter(**{field: artist_id})
        if portal:
            qs = qs.filter(**{f"{field}__in": allowed_artist_ids})
        return qs

    wanted = (
        set(filters.get("source_type", []))
        if isinstance(filters.get("source_type"), list)
        else ({filters["source_type"]} if filters.get("source_type") else set())
    )

    def include(source):
        return not wanted or source in wanted

    items = []
    if include("booking"):
        qs = artist_filter(
            Booking.objects.filter(
                organization=organization, event_date__range=(start.date(), end.date())
            )
            .exclude(status__in=[Booking.Status.CANCELLED, Booking.Status.DECLINED])
            .select_related("artist"),
            "artist_id",
        )
        for o in qs:
            items.append(
                _item(
                    "booking",
                    o,
                    o.title,
                    o.event_start_datetime or o.event_date,
                    o.event_end_datetime,
                    o.artist,
                    o.status,
                    f"/workspace/bookings/{o.pk}",
                    o.priority,
                    not o.event_start_datetime,
                )
            )
    if include("callsheet"):
        qs = CallSheetVersion.objects.filter(
            call_sheet__organization=organization,
            status=CallSheetVersion.Status.PUBLISHED,
            event_date__range=(start.date(), end.date()),
        ).select_related("call_sheet__booking__artist")
        qs = artist_filter(qs, "call_sheet__booking__artist_id")
        for o in qs:
            items.append(
                _item(
                    "callsheet",
                    o.call_sheet,
                    o.title,
                    o.event_start_datetime or o.event_date,
                    o.event_end_datetime,
                    o.call_sheet.booking.artist,
                    o.status,
                    f"/workspace/bookings/{o.call_sheet.booking_id}/call-sheet",
                    all_day=not o.event_start_datetime,
                )
            )
    if include("release"):
        qs = artist_filter(
            Release.objects.filter(organization=organization)
            .exclude(status__in=[Release.Status.CANCELLED, Release.Status.ARCHIVED])
            .select_related("primary_artist"),
            "primary_artist_id",
        )
        for o in qs:
            date = o.release_datetime or o.planned_release_date
            if (
                date
                and start.date()
                <= (date.date() if isinstance(date, datetime) else date)
                <= end.date()
            ):
                items.append(
                    _item(
                        "release",
                        o,
                        o.title,
                        date,
                        artist=o.primary_artist,
                        status=o.status,
                        url=f"/workspace/music/releases/{o.pk}",
                        all_day=not isinstance(date, datetime),
                    )
                )
    if include("campaign"):
        qs = artist_filter(
            Campaign.objects.filter(organization=organization, start_date__lte=end.date())
            .filter(Q(end_date__gte=start.date()) | Q(end_date__isnull=True))
            .exclude(status__in=[Campaign.Status.CANCELLED, Campaign.Status.ARCHIVED])
            .select_related("artist"),
            "artist_id",
        )
        for o in qs:
            if o.start_date:
                items.append(
                    _item(
                        "campaign",
                        o,
                        o.name,
                        o.start_date,
                        o.end_date,
                        o.artist,
                        o.status,
                        f"/workspace/campaigns/{o.pk}",
                        o.priority,
                        True,
                    )
                )
    if not portal and include("rollout_milestone"):
        for o in (
            RolloutMilestone.objects.filter(
                rollout__organization=organization, target_date__range=(start.date(), end.date())
            )
            .exclude(status=RolloutMilestone.Status.CANCELLED)
            .select_related("rollout__campaign__artist")
        ):
            items.append(
                _item(
                    "rollout_milestone",
                    o,
                    o.title,
                    o.target_date,
                    artist=o.rollout.campaign.artist,
                    status=o.status,
                    url=f"/workspace/rollouts/{o.rollout_id}",
                    all_day=True,
                )
            )
    if not portal and include("rollout_task"):
        for o in (
            RolloutTask.objects.filter(
                rollout__organization=organization, due_date__range=(start.date(), end.date())
            )
            .exclude(status=RolloutTask.Status.CANCELLED)
            .select_related("rollout__campaign__artist")
        ):
            items.append(
                _item(
                    "rollout_task",
                    o,
                    o.title,
                    o.due_date,
                    artist=o.rollout.campaign.artist,
                    status=o.status,
                    url=f"/workspace/rollouts/{o.rollout_id}",
                    priority=o.priority,
                    all_day=True,
                )
            )
    if include("calendar_event"):
        qs = (
            visible_events(user, organization)
            .filter(starts_at__lte=end)
            .filter(Q(ends_at__gte=start) | Q(ends_at__isnull=True))
            .exclude(status__in=[CalendarEvent.Status.CANCELLED, CalendarEvent.Status.ARCHIVED])
        )
        if artist_id:
            qs = qs.filter(artist_id=artist_id)
        if portal:
            qs = qs.filter(
                visibility=CalendarEvent.Visibility.ARTIST_TEAM, artist_id__in=allowed_artist_ids
            )
        for o in qs:
            items.append(
                _item(
                    "calendar_event",
                    o,
                    o.title,
                    o.starts_at,
                    o.ends_at,
                    o.artist,
                    o.status,
                    f"/workspace/calendar?event={o.pk}",
                    all_day=o.all_day,
                )
            )
    if filters.get("status"):
        items = [i for i in items if i["status"] == filters["status"]]
    if filters.get("priority"):
        items = [i for i in items if i["priority"] == filters["priority"]]
    return sorted(items, key=lambda i: i["starts_at"])
