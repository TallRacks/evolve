from django.db.models import Q

from artists.selectors import portal_artists_for_user
from organizations.permissions import user_has_organization_permission

from .models import Document


def documents_for_user(user, organization):
    qs = (
        Document.objects.filter(organization=organization)
        .select_related("uploaded_by", "parent_document")
        .prefetch_related(
            "links__artist",
            "links__booking",
            "links__call_sheet",
            "links__release",
            "links__campaign",
        )
    )
    if user.is_superuser:
        return qs
    if not user_has_organization_permission(user, organization, "document.view"):
        return qs.none()
    collaborator = Q(collaborators__user=user)
    qs = qs.filter(~Q(visibility=Document.Visibility.PRIVATE) | Q(uploaded_by=user) | collaborator)
    if not user_has_organization_permission(user, organization, "document.restricted.view"):
        qs = qs.filter(
            ~Q(visibility=Document.Visibility.RESTRICTED) | Q(uploaded_by=user) | collaborator
        )
    if not user_has_organization_permission(user, organization, "contract.view"):
        qs = qs.exclude(contract_links__isnull=False)
    if not user_has_organization_permission(user, organization, "rights.view"):
        qs = qs.exclude(works__isnull=False)
    if not user_has_organization_permission(user, organization, "royalties.view"):
        qs = qs.exclude(royalty_statements__isnull=False)
    return qs.distinct()


def portal_documents(user, organization):
    artist_ids = portal_artists_for_user(user).filter(organization=organization).values("pk")
    return (
        Document.objects.filter(
            organization=organization,
            visibility=Document.Visibility.ARTIST,
            links__artist_id__in=artist_ids,
        )
        .select_related("uploaded_by")
        .prefetch_related("links__artist")
        .distinct()
    )


def developer_documents(organization):
    return Document.objects.filter(
        organization=organization,
        visibility=Document.Visibility.ORGANIZATION,
        status=Document.Status.ACTIVE,
    ).prefetch_related(
        "links__artist", "links__booking", "links__call_sheet", "links__release", "links__campaign"
    )
