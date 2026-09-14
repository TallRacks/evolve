import secrets
import uuid
from pathlib import PurePath

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .file_validation import validate_upload
from .models import Document, DocumentLink, OfficeDocumentContent
from .storage import (
    DocumentStorageUnavailable,
    default_storage_provider,
    ensure_storage_key,
    get_storage_backend,
)


def require(user, organization, permission):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionError("Permission denied.")


def create_document(*, actor, organization, request=None, **data):
    require(actor, organization, "document.manage")
    data.setdefault("source_type", Document.SourceType.EXTERNAL)
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
        "source_type",
        "storage_provider",
        "storage_key",
        "storage_status",
        "original_filename",
        "content_type",
        "detected_content_type",
        "file_size",
        "checksum_sha256",
        "uploaded_at",
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
    updates = {"status": Document.Status.ARCHIVED, "archived_at": timezone.now()}
    if document.source_type == Document.SourceType.STORED:
        updates["storage_status"] = Document.StorageStatus.ARCHIVED
    Document.objects.filter(pk=document.pk).update(**updates)
    document.refresh_from_db()
    record_event(
        actor=actor,
        organization=document.organization,
        action="document.archived",
        resource=document,
        description="Document archived; retained file content was not deleted.",
        request=request,
    )
    return document


@transaction.atomic
def restore_document(document, *, actor, request=None):
    require(actor, document.organization, "document.manage")
    if document.status != Document.Status.ARCHIVED:
        return document
    updates = {"status": Document.Status.ACTIVE, "archived_at": None}
    if document.source_type == Document.SourceType.STORED:
        updates["storage_status"] = Document.StorageStatus.AVAILABLE
    Document.objects.filter(pk=document.pk).update(**updates)
    document.refresh_from_db()
    record_event(actor=actor, organization=document.organization, action="document.restored", resource=document, description="Document restored; retained content remains available.", request=request)
    return document


@transaction.atomic
def duplicate_office_document(document, *, actor, request=None, title=None):
    require(actor, document.organization, "document.manage")
    content = getattr(document, "office_content", None)
    if content is None:
        raise ValueError("Only native Office documents can be duplicated.")
    copy = Document.objects.create(organization=document.organization, workspace=document.workspace, title=(title or f"Copy of {document.title}")[:220], document_type=document.document_type, description=document.description, source_type=Document.SourceType.GENERATED, rendered_content="Office document", uploaded_by=actor, visibility=document.visibility)
    OfficeDocumentContent.objects.create(document=copy, format=content.format, content_json=content.content_json, last_edited_by=actor, last_edited_at=timezone.now())
    _copy_links(document, copy)
    record_event(actor=actor, organization=document.organization, action="document.duplicated", resource=copy, description=f"Created a native Office copy of {document.title}.", request=request)
    return copy


@transaction.atomic
def move_document_to_workspace(document, *, actor, workspace, request=None):
    require(actor, document.organization, "document.manage")
    if workspace is not None and workspace.organization_id != document.organization_id:
        raise ValueError("Documents can only move within their organization.")
    if workspace is not None and workspace.archived:
        raise ValueError("Documents cannot move to an archived workspace.")
    if document.workspace_id == getattr(workspace, "pk", None):
        return document
    document.workspace = workspace
    document.save(update_fields=("workspace", "updated_at"))
    record_event(actor=actor, organization=document.organization, action="document.moved", resource=document, description=(f"Moved Office document to {workspace.name}." if workspace else "Moved Office document to organization documents."), request=request)
    return document


@transaction.atomic
def create_version(document, *, actor, request=None, **data):
    require(actor, document.organization, "document.manage")
    root_id = document.parent_document_id or document.pk
    root = Document.objects.select_for_update().get(pk=root_id)
    latest_number = (
        Document.objects.filter(Q(parent_document=root) | Q(pk=root.pk)).aggregate(
            value=Max("version_number")
        )["value"]
        or 0
    )
    version = Document(
        organization=document.organization,
        parent_document=root,
        version_number=latest_number + 1,
        uploaded_by=actor,
        title=data.pop("title", document.title),
        document_type=data.pop("document_type", document.document_type),
        visibility=data.pop("visibility", document.visibility),
        **data,
    )
    version.save()
    _copy_links(document, version)
    record_event(
        actor=actor,
        organization=document.organization,
        action="document.version_created",
        resource=version,
        description="Document version created.",
        request=request,
    )
    return version


def _object_key(provider, organization_id, root_id, version_id, filename):
    suffix = PurePath(filename).suffix.lower()
    parts = [
        provider.path_prefix.strip("/"),
        "organizations",
        str(organization_id),
        "documents",
        str(root_id),
        str(version_id),
        f"{secrets.token_hex(16)}{suffix}",
    ]
    key = "/".join(part for part in parts if part)
    ensure_storage_key(key)
    return key


def _copy_links(source, target):
    for link in source.links.all():
        DocumentLink.objects.create(document=target, **{link.entity_type: link.entity})


def _upload_document(*, document, file, actor, request, action, source_for_links=None):
    metadata = validate_upload(file, document_type=document.document_type)
    provider = default_storage_provider()
    root_id = document.parent_document_id or document.pk
    key = _object_key(
        provider,
        document.organization_id,
        root_id,
        document.pk,
        metadata["original_filename"],
    )
    backend = get_storage_backend(provider)
    backend.put(
        key,
        file,
        metadata["detected_content_type"],
        {
            "organization": str(document.organization_id),
            "document": str(document.pk),
        },
    )
    try:
        with transaction.atomic():
            document.source_type = Document.SourceType.STORED
            document.storage_provider = provider
            document.storage_key = key
            document.storage_status = Document.StorageStatus.AVAILABLE
            document.uploaded_at = timezone.now()
            for field, value in metadata.items():
                setattr(document, field, value)
            document.save()
            if source_for_links:
                _copy_links(source_for_links, document)
            record_event(
                actor=actor,
                organization=document.organization,
                action=action,
                resource=document,
                description=(
                    f"Stored Document version {document.version_number}; "
                    f"{document.file_size} bytes; {document.detected_content_type}."
                ),
                request=request,
            )
    except Exception:
        try:
            backend.delete(key)
        except DocumentStorageUnavailable:
            pass
        raise
    return document


def upload_document(*, actor, organization, file, request=None, **data):
    require(actor, organization, "document.manage")
    document = Document(
        id=uuid.uuid4(),
        organization=organization,
        uploaded_by=actor,
        title=data["title"],
        document_type=data["document_type"],
        description=data.get("description", ""),
        visibility=data.get("visibility", Document.Visibility.ORGANIZATION),
    )
    return _upload_document(
        document=document,
        file=file,
        actor=actor,
        request=request,
        action="document.file_uploaded",
    )


def upload_new_version(*, document, actor, file, request=None, version_note=""):
    require(actor, document.organization, "document.manage")
    root_id = document.parent_document_id or document.pk
    with transaction.atomic():
        root = Document.objects.select_for_update().get(pk=root_id)
        latest = (
            Document.objects.filter(Q(parent_document=root) | Q(pk=root.pk))
            .order_by("-version_number")
            .first()
        )
        version = Document(
            id=uuid.uuid4(),
            organization=document.organization,
            parent_document=root,
            version_number=latest.version_number + 1,
            uploaded_by=actor,
            title=document.title,
            document_type=document.document_type,
            description=version_note or document.description,
            visibility=document.visibility,
        )
        return _upload_document(
            document=version,
            file=file,
            actor=actor,
            request=request,
            action="document.version_uploaded",
            source_for_links=document,
        )


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
