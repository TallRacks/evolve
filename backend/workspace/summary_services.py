from django.utils import timezone

from bookings.models import Booking
from music.models import Release
from notifications.selectors import unread_count
from tasks.models import Task
from tasks.selectors import tasks_for_user


def daily_summary(*, user, organization, on=None):
    day = on or timezone.localdate()
    tasks = (
        tasks_for_user(user)
        .filter(organization=organization)
        .exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])
    )
    due = tasks.filter(due_at__date=day)
    overdue = tasks.filter(due_at__lt=timezone.now())
    bookings = Booking.objects.filter(organization=organization, event_date=day).select_related(
        "artist", "venue"
    )
    releases = Release.objects.filter(
        organization=organization, planned_release_date__gte=day
    ).order_by("planned_release_date")[:10]
    return {
        "date": day,
        "bookings": [
            {
                "id": str(x.id),
                "reference": x.reference,
                "title": x.title,
                "venue": x.venue.name if x.venue else None,
            }
            for x in bookings
        ],
        "tasks_due": [{"id": str(x.id), "title": x.title, "due_at": x.due_at} for x in due[:50]],
        "overdue_tasks": [
            {"id": str(x.id), "title": x.title, "due_at": x.due_at} for x in overdue[:50]
        ],
        "upcoming_releases": [
            {"id": str(x.id), "title": x.title, "release_date": x.planned_release_date}
            for x in releases
        ],
        "unread_notifications": unread_count(user),
        "needs_attention": {"overdue_tasks": overdue.count()},
    }


def workspace_summary(*, user, workspace):
    organization = workspace.organization
    tasks = (
        tasks_for_user(user)
        .filter(organization=organization)
        .exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])
    )
    bookings = Booking.objects.filter(
        organization=organization, event_date__gte=timezone.localdate()
    ).select_related("artist", "venue")[:10]
    releases = Release.objects.filter(
        organization=organization, planned_release_date__gte=timezone.localdate()
    ).order_by("planned_release_date")[:10]
    return {
        "workspace": {"id": str(workspace.id), "name": workspace.name},
        "open_tasks": tasks.count(),
        "overdue_tasks": tasks.filter(due_at__lt=timezone.now()).count(),
        "upcoming_bookings": [
            {
                "id": str(x.id),
                "reference": x.reference,
                "date": x.event_date,
                "venue": x.venue.name if x.venue else None,
            }
            for x in bookings
        ],
        "upcoming_releases": [
            {"id": str(x.id), "title": x.title, "release_date": x.planned_release_date}
            for x in releases
        ],
        "boards": [
            {"id": str(x.id), "name": x.name, "source": x.source_type}
            for x in workspace.boards.filter(archived=False)
        ],
    }


def booking_summary(*, user, booking):
    tasks = (
        tasks_for_user(user)
        .filter(organization=booking.organization, context_type="booking", context_id=booking.id)
        .exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])
    )
    return {
        "id": str(booking.id),
        "reference": booking.reference,
        "date": booking.event_date,
        "venue": booking.venue.name if booking.venue else None,
        "status": booking.status,
        "readiness": getattr(booking, "readiness", None),
        "next_action": getattr(booking, "next_action", None),
        "open_tasks": [{"id": str(x.id), "title": x.title, "due_at": x.due_at} for x in tasks[:50]],
    }


def release_summary(*, user, release):
    return {
        "id": str(release.id),
        "title": release.title,
        "release_date": release.planned_release_date,
        "status": release.status,
        "readiness": getattr(release, "readiness", None),
        "next_action": getattr(release, "next_action", None),
        "tracks": release.release_tracks.count(),
    }
