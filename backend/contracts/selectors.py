from artists.selectors import portal_artists_for_user
from audit.models import AuditEvent
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user

from .models import Contract


def contract_queryset():
    return Contract.objects.select_related(
        "organization", "artist", "booking", "promoter", "created_by"
    ).prefetch_related(
        "parties", "terms", "sections", "approvals__membership__user", "document_links__document"
    )


def contracts_for_user(user):
    if not user or not user.is_authenticated or not user.is_active:
        return contract_queryset().none()
    if user.is_superuser:
        return contract_queryset()
    organizations = [
        org
        for org in organizations_for_user(user)
        if user_has_organization_permission(user, org, "contract.view")
    ]
    return contract_queryset().filter(organization__in=organizations)


def artist_contracts_for_user(user):
    return contract_queryset().filter(
        artist_id__in=portal_artists_for_user(user).values("pk"), status=Contract.Status.EXECUTED
    )


def contract_activity(contract):
    ids = [
        str(contract.pk),
        *(str(x) for x in contract.parties.values_list("pk", flat=True)),
        *(str(x) for x in contract.terms.values_list("pk", flat=True)),
        *(str(x) for x in contract.sections.values_list("pk", flat=True)),
        *(str(x) for x in contract.approvals.values_list("pk", flat=True)),
        *(str(x) for x in contract.document_links.values_list("pk", flat=True)),
    ]
    return (
        AuditEvent.objects.filter(
            organization=contract.organization, resource_id__in=ids, action__startswith="contract."
        )
        .select_related("actor")
        .order_by("-created_at")[:100]
    )
