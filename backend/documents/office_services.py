import json
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Document, DocumentRevision, OfficeDocumentContent

ALLOWED_NODES = {
    "doc",
    "paragraph",
    "heading",
    "bullet_list",
    "ordered_list",
    "list_item",
    "checklist",
    "check_item",
    "blockquote",
    "callout",
    "table",
    "table_row",
    "table_cell",
    "divider",
    "text",
    "image",
    "link",
}
ALLOWED_FORMATS = {choice.value for choice in OfficeDocumentContent.Format}


def validate_content(value, depth=0):
    if depth > 30:
        raise ValidationError("Office content is too deeply nested.")
    if not isinstance(value, dict | list):
        raise ValidationError("Office content must be structured JSON.")
    if isinstance(value, list):
        for item in value:
            validate_content(item, depth + 1)
        return
    node_type = value.get("type")
    if node_type not in ALLOWED_NODES:
        raise ValidationError("Office content contains an unsupported node.")
    if "text" in value and (not isinstance(value["text"], str) or len(value["text"]) > 20000):
        raise ValidationError("Office text is invalid.")
    if node_type in {"link", "image"}:
        attrs = value.get("attrs", {})
        if not isinstance(attrs, dict):
            raise ValidationError("Office node attributes are invalid.")
        if node_type == "link" and not str(attrs.get("href", "")).lower().startswith(
            ("https://", "http://")
        ):
            raise ValidationError("Only HTTP(S) links are supported.")
    if "content" in value:
        validate_content(value["content"], depth + 1)
    if "attrs" in value and not isinstance(value["attrs"], dict):
        raise ValidationError("Office node attributes are invalid.")
    if len(json.dumps(value, separators=(",", ":"))) > 1_000_000:
        raise ValidationError("Office content exceeds the 1 MB limit.")


def initial_content():
    return {"type": "doc", "content": [{"type": "paragraph", "content": []}]}


def require(actor, document, permission="document.view"):
    if not user_has_organization_permission(actor, document.organization, permission):
        raise PermissionError("Permission denied.")


def create_office_document(
    *, actor, organization, title, document_type, format, visibility, workspace=None, request=None
):
    if not user_has_organization_permission(actor, organization, "document.manage"):
        raise PermissionError("Permission denied.")
    if format not in ALLOWED_FORMATS:
        raise ValidationError("Unsupported Office format.")
    document = Document.objects.create(
        organization=organization,
        workspace=workspace,
        title=title,
        document_type=document_type,
        visibility=visibility,
        source_type=Document.SourceType.GENERATED,
        rendered_content="Office document",
        uploaded_by=actor,
    )
    OfficeDocumentContent.objects.create(
        document=document,
        format=format,
        content_json=initial_content(),
        last_edited_by=actor,
        last_edited_at=timezone.now(),
    )
    record_event(
        actor=actor,
        organization=organization,
        action="document.created",
        resource=document,
        description="Created native Office document.",
        request=request,
    )
    return document


@transaction.atomic
def save_content(*, actor, document, content, expected_revision, change_summary="", request=None):
    require(actor, document, "document.manage")
    validate_content(content)
    current = OfficeDocumentContent.objects.select_for_update().filter(document=document).first()
    if not current:
        current = OfficeDocumentContent.objects.create(
            document=document,
            format=OfficeDocumentContent.Format.DOCUMENT,
            content_json=initial_content(),
        )
    if current.revision_number != expected_revision:
        raise ValueError("CONFLICT")
    next_revision = current.revision_number + 1
    DocumentRevision.objects.create(
        document=document,
        revision_number=next_revision,
        content_json=deepcopy(content),
        created_by=actor,
        change_summary=change_summary,
    )
    current.content_json = content
    current.revision_number = next_revision
    current.last_edited_by = actor
    current.last_edited_at = timezone.now()
    current.save()
    return current


@transaction.atomic
def restore_revision(*, actor, document, revision_number, request=None):
    require(actor, document, "document.manage")
    revision = DocumentRevision.objects.get(document=document, revision_number=revision_number)
    current = OfficeDocumentContent.objects.select_for_update().get(document=document)
    return save_content(
        actor=actor,
        document=document,
        content=revision.content_json,
        expected_revision=current.revision_number,
        change_summary=f"Restored revision {revision_number}",
        request=request,
    )
