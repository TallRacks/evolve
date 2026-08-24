from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Document, DocumentLink


def require(user, organization, permission):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionError("Permission denied.")


def create_document(*, actor, organization, request=None, **data):
    require(actor, organization, "document.manage")
    document = Document(organization=organization, uploaded_by=actor, **data)
    document.save()
    record_event(
        actor=actor,
        organization=organization,
        action="document.created",
        resource=document,
        description="Document metadata created.",
        request=request,
    )
    return document


def update_document(document, *, actor, request=None, **data):
    require(actor, document.organization, "document.manage")
    for protected in (
        "status",
        "storage_key",
        "checksum_sha256",
        "parent_document",
        "version_number",
    ):
        data.pop(protected, None)
    for key, value in data.items():
        setattr(document, key, value)
    document.save()
    record_event(
        actor=actor,
        organization=document.organization,
        action="document.updated",
        resource=document,
        description="Document metadata updated.",
        request=request,
    )
    return document


@transaction.atomic
def archive_document(document, *, actor, request=None):
    require(actor, document.organization, "document.manage")
    Document.objects.filter(pk=document.pk).update(
        status=Document.Status.ARCHIVED, archived_at=timezone.now()
    )
    document.refresh_from_db()
    record_event(
        actor=actor,
        organization=document.organization,
        action="document.archived",
        resource=document,
        description="Document metadata archived.",
        request=request,
    )
    return document


@transaction.atomic
def create_version(document, *, actor, request=None, **data):
    require(actor, document.organization, "document.manage")
    root = document.parent_document or document
    latest = (
        Document.objects.select_for_update()
        .filter(Q(parent_document=root) | Q(pk=root.pk))
        .order_by("-version_number")
        .first()
    )
    version = Document(
        organization=document.organization,
        parent_document=root,
        version_number=latest.version_number + 1,
        uploaded_by=actor,
        title=data.pop("title", document.title),
        document_type=data.pop("document_type", document.document_type),
        visibility=data.pop("visibility", document.visibility),
        **data,
    )
    version.save()
    record_event(
        actor=actor,
        organization=document.organization,
        action="document.version_created",
        resource=version,
        description="Document version created.",
        request=request,
    )
    return version


def link_document(document, *, actor, request=None, **entity):
    require(actor, document.organization, "document.manage")
    link = DocumentLink(document=document, **entity)
    link.save()
    record_event(
        actor=actor,
        organization=document.organization,
        action="document.linked",
        resource=document,
        description=f"Document linked to {link.entity_type}.",
        request=request,
    )
    return link


def unlink_document(link, *, actor, request=None):
    require(actor, link.document.organization, "document.manage")
    record_event(
        actor=actor,
        organization=link.document.organization,
        action="document.unlinked",
        resource=link.document,
        description=f"Document unlinked from {link.entity_type}.",
        request=request,
    )
    DocumentLink.objects.filter(pk=link.pk).delete()
