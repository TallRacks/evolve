from django.db.models import Q

from artists.selectors import portal_artists_for_user
from audit.models import AuditEvent
from organizations.selectors import organizations_for_user

from .models import ProductionAdvance


def advance_queryset():
    return ProductionAdvance.objects.select_related(
        "organization", "booking", "artist", "venue", "promoter", "created_by"
    ).prefetch_related(
        "requirements__assigned_membership__user",
        "contact_assignments__contact",
        "schedule_items",
        "checklist_items__assigned_membership__user",
    )


def advances_for_user(user):
    if not user or not user.is_authenticated or not user.is_active:
        return advance_queryset().none()
    if user.is_superuser:
        return advance_queryset()
    return advance_queryset().filter(organization_id__in=organizations_for_user(user).values("pk"))


def artist_advances_for_user(user):
    return (
        advance_queryset()
        .filter(artist_id__in=portal_artists_for_user(user).values("pk"))
        .exclude(status=ProductionAdvance.Status.ARCHIVED)
    )


def advance_activity(advance):
    child_ids = [
        *(str(value) for value in advance.requirements.values_list("pk", flat=True)),
        *(str(value) for value in advance.contact_assignments.values_list("pk", flat=True)),
        *(str(value) for value in advance.schedule_items.values_list("pk", flat=True)),
        *(str(value) for value in advance.checklist_items.values_list("pk", flat=True)),
    ]
    return (
        AuditEvent.objects.filter(
            Q(resource_id=str(advance.pk)) | Q(resource_id__in=child_ids),
            organization=advance.organization,
            action__startswith="production.",
        )
        .select_related("actor")
        .order_by("-created_at")[:100]
    )
