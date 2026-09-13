import json
import uuid
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Document, DocumentRevision, OfficeDocumentAttachment, OfficeDocumentContent

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
    "sheet",
    "sheet_column",
    "sheet_row",
}
ALLOWED_FORMATS = {choice.value for choice in OfficeDocumentContent.Format}


def validate_content(value, depth=0):
    if isinstance(value, dict) and value.get("type") == "sheet":
        validate_sheet(value)
        return
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
        if node_type == "image" and (not attrs.get("attachment_id") or "src" in attrs):
            raise ValidationError("Images must reference a private attachment ID.")
    if "content" in value:
        validate_content(value["content"], depth + 1)
    if "attrs" in value and not isinstance(value["attrs"], dict):
        raise ValidationError("Office node attributes are invalid.")
    if len(json.dumps(value, separators=(",", ":"))) > 1_000_000:
        raise ValidationError("Office content exceeds the 1 MB limit.")


SHEET_TYPES = {
    "TEXT",
    "NUMBER",
    "DATE",
    "DATETIME",
    "CURRENCY",
    "STATUS",
    "SELECT",
    "CHECKBOX",
    "USER",
    "ENTITY_LINK",
}
SHEET_ENTITIES = {"artist", "booking", "release", "task", "contact", "venue", "promoter"}


def validate_sheet(value):
    if not isinstance(value, dict) or value.get("type") != "sheet":
        raise ValidationError("Sheet content must be a structured sheet object.")
    columns = value.get("columns", [])
    rows = value.get("rows", [])
    if (
        not isinstance(columns, list)
        or not isinstance(rows, list)
        or len(columns) > 200
        or len(rows) > 10000
    ):
        raise ValidationError("Sheet dimensions exceed the supported limit.")
    column_ids = set()
    for column in columns:
        if not isinstance(column, dict) or not column.get("id") or not column.get("name"):
            raise ValidationError("Sheet columns require an id and name.")
        if column["id"] in column_ids or column.get("type", "TEXT") not in SHEET_TYPES:
            raise ValidationError("Sheet column type or identity is invalid.")
        if column.get("type") == "ENTITY_LINK" and column.get("entity") not in SHEET_ENTITIES:
            raise ValidationError("Sheet entity links use an unsupported registry entry.")
        column_ids.add(column["id"])
    for row in rows:
        if (
            not isinstance(row, dict)
            or not row.get("id")
            or not isinstance(row.get("cells", {}), dict)
        ):
            raise ValidationError("Sheet rows require an id and cells object.")
        if set(row["cells"]) - column_ids:
            raise ValidationError("Sheet cells must reference declared columns.")
        for column in columns:
            cell = row["cells"].get(column["id"])
            if cell in (None, ""):
                continue
            cell_type = column.get("type", "TEXT")
            if cell_type in {"NUMBER", "CURRENCY"}:
                try:
                    Decimal(str(cell))
                except (InvalidOperation, TypeError, ValueError) as exc:
                    raise ValidationError("Number and currency cells must be numeric.") from exc
            elif cell_type == "DATE":
                try:
                    date.fromisoformat(str(cell))
                except ValueError as exc:
                    raise ValidationError("Date cells must use ISO date format.") from exc
            elif cell_type == "DATETIME":
                try:
                    datetime.fromisoformat(str(cell).replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValidationError("Datetime cells must use ISO datetime format.") from exc
            elif cell_type == "CHECKBOX" and not isinstance(cell, bool | str):
                raise ValidationError("Checkbox cells must be boolean values.")
            elif cell_type in {
                "TEXT",
                "STATUS",
                "SELECT",
                "USER",
                "ENTITY_LINK",
            } and not isinstance(cell, str | dict):
                raise ValidationError("Sheet cell value has an invalid type.")
    if len(json.dumps(value, separators=(",", ":"))) > 2_000_000:
        raise ValidationError("Sheet content exceeds the 2 MB limit.")


def _walk_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_nodes(child)


def initial_content(format=None):
    if format == OfficeDocumentContent.Format.SHEET:
        return {"type": "sheet", "columns": [], "rows": []}
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
        content_json=initial_content(format),
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
    for node in _walk_nodes(content):
        if isinstance(node, dict) and node.get("type") == "image":
            if not OfficeDocumentAttachment.objects.filter(
                id=node.get("attrs", {}).get("attachment_id"),
                office_document=document,
                is_image=True,
                attachment__status=Document.Status.ACTIVE,
                attachment__storage_status=Document.StorageStatus.AVAILABLE,
            ).exists():
                raise ValidationError(
                    "Image references must point to an authorized image attachment."
                )
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


def mutate_sheet(sheet, operation, payload):
    """Apply one allowlisted structural change to a Sheet JSON object."""
    if not isinstance(sheet, dict) or sheet.get("type") != "sheet":
        raise ValidationError("Sheet content must be a structured sheet object.")
    result = deepcopy(sheet)
    columns = result.setdefault("columns", [])
    rows = result.setdefault("rows", [])
    ids = {column["id"] for column in columns}

    def reorder_delta():
        try:
            delta = int(payload.get("delta", 0))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Reorder delta is invalid.") from exc
        if delta not in {-1, 1}:
            raise ValidationError("Reorder delta must be -1 or 1.")
        return delta

    def validate_options(options):
        if not isinstance(options, list) or any(
            not isinstance(item, dict) or not item.get("key") or not item.get("label")
            for item in options
        ):
            raise ValidationError("Select and status columns require labelled options.")
        keys = [item["key"] for item in options]
        if len(keys) != len(set(keys)):
            raise ValidationError("Select and status option keys must be unique.")

    if operation == "add_column":
        column = payload.get("column")
        if not isinstance(column, dict) or not column.get("name"):
            raise ValidationError("Column name is required.")
        column = deepcopy(column)
        column.setdefault("id", f"column_{uuid.uuid4().hex[:12]}")
        column.setdefault("type", "TEXT")
        if column["id"] in ids or column["type"] not in SHEET_TYPES:
            raise ValidationError("Column identity or type is invalid.")
        if column["type"] in {"SELECT", "STATUS"}:
            options = column.get("options", [])
            validate_options(options)
        columns.append(column)
        for row in rows:
            row.setdefault("cells", {})[column["id"]] = ""
    elif operation in {
        "rename_column",
        "configure_column",
        "change_column_type",
        "remove_column",
        "move_column",
    }:
        column_id = payload.get("column_id")
        column = next((item for item in columns if item.get("id") == column_id), None)
        if not column:
            raise ValidationError("Column was not found.")
        if operation == "rename_column":
            name = str(payload.get("name", "")).strip()
            if not name:
                raise ValidationError("Column name is required.")
            column["name"] = name[:120]
        elif operation == "configure_column":
            options = payload.get("options", [])
            if column.get("type") not in {"SELECT", "STATUS"}:
                raise ValidationError("Controlled options are invalid for this column.")
            validate_options(options)
            column["options"] = deepcopy(options)
        elif operation == "change_column_type":
            new_type = payload.get("type")
            if new_type not in SHEET_TYPES:
                raise ValidationError("Unsupported column type.")
            incompatible = []
            for row in rows:
                value = row.get("cells", {}).get(column_id)
                if value in (None, ""):
                    continue
                try:
                    validate_sheet(
                        {
                            "type": "sheet",
                            "columns": [
                                {"id": column_id, "name": column["name"], "type": new_type}
                            ],
                            "rows": [{"id": row["id"], "cells": {column_id: value}}],
                        }
                    )
                except ValidationError:
                    incompatible.append(row["id"])
            if incompatible:
                raise ValidationError(f"{len(incompatible)} cells cannot be converted.")
            column["type"] = new_type
        elif operation == "remove_column":
            if any(
                row.get("cells", {}).get(column_id) not in (None, "") for row in rows
            ) and not payload.get("confirmed"):
                raise ValidationError("Removing a populated column requires confirmation.")
            columns.remove(column)
            for row in rows:
                row.get("cells", {}).pop(column_id, None)
        else:
            index = columns.index(column)
            new_index = max(0, min(len(columns) - 1, index + reorder_delta()))
            columns.insert(new_index, columns.pop(index))
    elif operation in {
        "add_row",
        "insert_row",
        "duplicate_row",
        "delete_row",
        "bulk_delete_rows",
        "move_row",
    }:
        if operation == "add_row" or operation == "insert_row":
            values = payload.get("cells", {})
            if not isinstance(values, dict):
                raise ValidationError("Row cells must be an object.")
            row = {
                "id": f"row_{uuid.uuid4().hex[:12]}",
                "cells": {column["id"]: values.get(column["id"], "") for column in columns},
            }
            validate_sheet({"type": "sheet", "columns": columns, "rows": [row]})
            if operation == "insert_row":
                try:
                    index = int(payload.get("index", len(rows)))
                except (TypeError, ValueError) as exc:
                    raise ValidationError("Row insertion index is invalid.") from exc
            else:
                index = len(rows)
            rows.insert(max(0, min(len(rows), index)), row)
        elif operation == "duplicate_row":
            source = next((item for item in rows if item.get("id") == payload.get("row_id")), None)
            if not source:
                raise ValidationError("Row was not found.")
            row = {"id": f"row_{uuid.uuid4().hex[:12]}", "cells": deepcopy(source.get("cells", {}))}
            rows.insert(rows.index(source) + 1, row)
        elif operation == "delete_row" or operation == "move_row":
            row = next((item for item in rows if item.get("id") == payload.get("row_id")), None)
            if not row:
                raise ValidationError("Row was not found.")
            if operation == "delete_row":
                rows.remove(row)
            else:
                index = rows.index(row)
                new_index = max(0, min(len(rows) - 1, index + reorder_delta()))
                rows.insert(new_index, rows.pop(index))
        else:
            row_ids = payload.get("row_ids", [])
            if not isinstance(row_ids, list) or any(not isinstance(item, str) for item in row_ids):
                raise ValidationError("Row selection is invalid.")
            rows[:] = [row for row in rows if row.get("id") not in row_ids]
    else:
        raise ValidationError("Unsupported Sheet operation.")
    validate_sheet(result)
    return result
