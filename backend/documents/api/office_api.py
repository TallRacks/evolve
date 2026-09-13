from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Document, DocumentRevision, OfficeDocumentContent
from documents.office_services import create_office_document, restore_revision, save_content
from documents.selectors import documents_for_user
from organizations.selectors import organizations_for_user
from workspace.models import Workspace


def organization_for(request):
    return get_object_or_404(
        organizations_for_user(request.user),
        pk=request.data.get("organization_id") or request.query_params.get("organization_id"),
    )


def document_for(request, document_id):
    organization = organization_for(request)
    queryset = documents_for_user(request.user, organization)
    workspace_id = request.data.get("workspace_id") or request.query_params.get("workspace_id")
    if workspace_id:
        queryset = queryset.filter(workspace_id=workspace_id)
    return get_object_or_404(queryset, pk=document_id)


def content_response(document):
    content = getattr(document, "office_content", None)
    if not content:
        return {
            "document": str(document.id),
            "title": document.title,
            "format": None,
            "content_json": None,
            "revision_number": 0,
        }
    return {
        "document": str(document.id),
        "title": document.title,
        "format": content.format,
        "content_json": content.content_json,
        "revision_number": content.revision_number,
        "last_edited_at": content.last_edited_at,
    }


class OfficeDocumentCollectionView(APIView):
    def post(self, request):
        organization = organization_for(request)
        workspace = None
        workspace_id = request.data.get("workspace_id") or request.query_params.get("workspace_id")
        if workspace_id:
            workspace = get_object_or_404(
                Workspace,
                pk=workspace_id,
                organization=organization,
                archived=False,
            )
        try:
            document = create_office_document(
                actor=request.user,
                organization=organization,
                workspace=workspace,
                title=str(request.data.get("title", "")).strip(),
                document_type=request.data.get("document_type", Document.Type.OTHER),
                format=request.data.get("format", OfficeDocumentContent.Format.DOCUMENT),
                visibility=request.data.get("visibility", Document.Visibility.ORGANIZATION),
                request=request,
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(content_response(document), status=201)


class OfficeContentView(APIView):
    def get(self, request, document_id):
        return Response(content_response(document_for(request, document_id)))

    def patch(self, request, document_id):
        document = document_for(request, document_id)
        try:
            save_content(
                actor=request.user,
                document=document,
                content=request.data.get("content_json"),
                expected_revision=int(request.data.get("expected_revision", -1)),
                change_summary=str(request.data.get("change_summary", "")),
                request=request,
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            if str(exc) == "CONFLICT":
                return Response(
                    {
                        "detail": "This document was changed by another user.",
                        "code": "conflict",
                        **content_response(document),
                    },
                    status=409,
                )
            raise ValidationError(str(exc)) from exc
        return Response(content_response(document))


class OfficeRevisionView(APIView):
    def get(self, request, document_id):
        document = document_for(request, document_id)
        return Response(
            [
                {
                    "id": str(row.id),
                    "revision_number": row.revision_number,
                    "content_json": row.content_json,
                    "created_by": row.created_by_id,
                    "created_at": row.created_at,
                    "change_summary": row.change_summary,
                }
                for row in document.office_revisions.select_related("created_by")
            ]
        )

    def post(self, request, document_id, revision_number):
        document = document_for(request, document_id)
        try:
            restore_revision(
                actor=request.user,
                document=document,
                revision_number=revision_number,
                request=request,
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except DocumentRevision.DoesNotExist as exc:
            raise ValidationError("Revision not found.") from exc
        return Response(content_response(document))


class OfficeDocumentListView(APIView):
    def get(self, request):
        organization = organization_for(request)
        rows = documents_for_user(request.user, organization).filter(office_content__isnull=False)
        workspace_id = request.query_params.get("workspace_id")
        if workspace_id:
            rows = rows.filter(workspace_id=workspace_id)
        rows = (rows
            .select_related("office_content")
        )
        return Response(
            [
                {
                    "id": str(row.id),
                    "title": row.title,
                    "format": row.office_content.format,
                    "visibility": row.visibility,
                    "workspace_id": str(row.workspace_id) if row.workspace_id else None,
                    "updated_at": row.updated_at,
                    "revision_number": row.office_content.revision_number,
                }
                for row in rows[:100]
            ]
        )


class OfficeSheetView(APIView):
    def get(self, request, document_id):
        document = document_for(request, document_id)
        content = document.office_content.content_json
        if content.get("type") != "sheet":
            content = {"type": "sheet", "columns": [], "rows": []}
        return Response({"document": str(document.id), "revision_number": document.office_content.revision_number, "sheet": content})

    def patch(self, request, document_id):
        document = document_for(request, document_id)
        current = document.office_content
        try:
            save_content(actor=request.user, document=document, content=request.data.get("sheet"), expected_revision=int(request.data.get("expected_revision", -1)), change_summary="Updated Sheet", request=request)
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            if str(exc) == "CONFLICT":
                return Response({"detail": "This Sheet changed since it was opened.", "code": "conflict", "revision_number": current.revision_number}, status=409)
            raise ValidationError(str(exc)) from exc
        return self.get(request, document_id)

    def post(self, request, document_id):
        document = document_for(request, document_id)
        if request.data.get("operation") != "import_csv":
            raise ValidationError("Unsupported Sheet operation.")
        csv_text = request.data.get("csv", "")
        if not isinstance(csv_text, str) or len(csv_text) > 2_000_000:
            raise ValidationError("CSV import is too large or invalid.")
        import csv
        from io import StringIO
        try:
            rows = list(csv.reader(StringIO(csv_text)))
        except csv.Error as exc:
            raise ValidationError("Malformed CSV.") from exc
        if not rows or len(rows) > 10001 or len(rows[0]) > 200:
            raise ValidationError("CSV dimensions exceed the supported limit.")
        columns = [{"id": f"column_{index + 1}", "name": name[:120] or f"Column {index + 1}", "type": "TEXT"} for index, name in enumerate(rows[0])]
        sheet = {
            "type": "sheet",
            "columns": columns,
            "rows": [
                {
                    "id": f"row_{index + 1}",
                    "cells": {
                        column["id"]: (
                            "'" + value[:19999]
                            if value[:1] in ("=", "+", "-", "@")
                            else value[:20000]
                        )
                        for column, value in zip(columns, row)
                    },
                }
                for index, row in enumerate(rows[1:], 1)
            ],
        }
        current = document.office_content
        save_content(actor=request.user, document=document, content=sheet, expected_revision=int(request.data.get("expected_revision", -1)), change_summary="Imported CSV", request=request)
        return self.get(request, document_id)

    def export(self, request, document_id):
        document = document_for(request, document_id)
        import csv
        from io import StringIO
        sheet = document.office_content.content_json
        output = StringIO()
        writer = csv.writer(output)
        columns = sheet.get("columns", [])
        writer.writerow([column.get("name", "") for column in columns])
        for row in sheet.get("rows", []):
            values = [str(row.get("cells", {}).get(column.get("id"), "")) for column in columns]
            writer.writerow([f"'" + value if value.startswith(("=", "+", "-", "@")) else value for value in values])
        response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{document.title[:80]}.csv"'
        return response


class OfficeSheetExportView(OfficeSheetView):
    def get(self, request, document_id):
        return self.export(request, document_id)
