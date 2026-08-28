from django.db.models import Q

from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user

from .models import Task

PROTECTED_CONTEXT_PERMISSIONS = {
    "contract_id": "contract.view",
}


def tasks_for_user(user):
    if not user or not user.is_authenticated or not user.is_active:
        return Task.objects.none()
    queryset = Task.objects.filter(archived_at__isnull=True)
    if not user.is_superuser:
        queryset = queryset.filter(organization_id__in=organizations_for_user(user).values("pk"))
    denied_contexts = Q(pk__isnull=True)
    for field, permission in PROTECTED_CONTEXT_PERMISSIONS.items():
        denied_organizations = [
            organization_id
            for organization_id in queryset.values_list("organization_id", flat=True).distinct()
            if not user_has_organization_permission(
                user,
                queryset.model.organization.field.related_model.objects.get(pk=organization_id),
                permission,
            )
        ]
        denied_contexts |= Q(
            **{f"{field}__isnull": False, "organization_id__in": denied_organizations}
        )
    allowed_organizations = [
        organization_id
        for organization_id in queryset.values_list("organization_id", flat=True).distinct()
        if user_has_organization_permission(
            user,
            queryset.model.organization.field.related_model.objects.get(pk=organization_id),
            "task.view",
        )
    ]
    return queryset.filter(organization_id__in=allowed_organizations).exclude(denied_contexts)
