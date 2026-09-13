from django.utils import timezone

from audit.models import AuditEvent
from bookings.models import Booking
from documents.models import OfficeDocumentContent
from documents.selectors import documents_for_user
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
    documents = documents_for_user(user, organization).filter(
        workspace=workspace, status="active"
    ).order_by("-updated_at")
    tasks = (
        tasks_for_user(user)
        .filter(source_document__workspace=workspace)
        .select_related("assigned_membership__user", "source_document")
    )
    board_ids = list(workspace.boards.values_list("id", flat=True))
    document_ids = list(documents.values_list("id", flat=True)[:100])
    task_ids = list(tasks.values_list("id", flat=True)[:100])
    resource_ids = [str(workspace.id), *(str(item) for item in board_ids)]
    resource_ids.extend(str(item) for item in document_ids)
    resource_ids.extend(str(item) for item in task_ids)
    activity = AuditEvent.objects.filter(
        organization=organization, resource_id__in=resource_ids
    ).select_related("actor")[:20]
    open_tasks = tasks.exclude(status__in=[Task.Status.DONE, Task.Status.CANCELLED])
    def document_format(item):
        try:
            return item.office_content.format
        except OfficeDocumentContent.DoesNotExist:
            return None

    return {
        "workspace": {
            "id": str(workspace.id),
            "name": workspace.name,
            "description": workspace.description,
            "icon": workspace.icon,
            "archived": workspace.archived,
        },
        "open_tasks": open_tasks.count(),
        "overdue_tasks": open_tasks.filter(due_at__lt=timezone.now()).count(),
        "tasks": [
            {"id": str(item.id), "title": item.title, "status": item.status, "due_at": item.due_at}
            for item in open_tasks[:10]
        ],
        "upcoming_bookings": [],
        "upcoming_releases": [],
        "boards": [
            {"id": str(item.id), "name": item.name, "source": item.source_type}
            for item in workspace.boards.filter(archived=False)
        ],
        "documents": [
            {"id": str(item.id), "title": item.title, "format": document_format(item)}
            for item in documents[:10]
        ],
        "recent_activity": [
            {
                "id": str(item.id),
                "action": item.action,
                "description": item.description,
                "created_at": item.created_at,
            }
            for item in activity
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
