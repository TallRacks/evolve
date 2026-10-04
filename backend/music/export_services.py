"""Deterministic CSV and PDF exports for music delivery workspaces."""

import csv
import io
import textwrap


def csv_safe(value):
    """Prevent spreadsheet formula execution in downloaded CSV files."""
    value = "" if value is None else str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def csv_response(filename, headers, rows):
    from django.http import HttpResponse

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow([csv_safe(value) for value in headers])
    for row in rows:
        writer.writerow([csv_safe(value) for value in row])
    response = HttpResponse(stream.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _pdf_escape(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_response(filename, title, lines):
    """Create a small text PDF without adding a binary dependency to the API."""
    from django.http import HttpResponse

    wrapped = []
    for line in [title, "", *lines]:
        wrapped.extend(textwrap.wrap(str(line), width=94) or [""])
    pages = [wrapped[index : index + 48] for index in range(0, len(wrapped), 48)] or [[]]
    objects = [
        None,
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_ids = []
    content_ids = []
    for page in pages:
        content = ["BT", "/F1 10 Tf", "50 750 Td", "14 TL"]
        for line in page:
            content.append(f"({_pdf_escape(line)}) Tj T*")
        content.append("ET")
        body = "\n".join(content).encode("latin-1", "replace")
        content_ids.append(len(objects) + 1)
        objects.append(f"<< /Length {len(body)} >>\nstream\n".encode() + body + b"\nendstream")
        page_ids.append(len(objects) + 1)
        objects.append(None)
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    for page_id, content_id in zip(page_ids, content_ids, strict=False):
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 4 0 R >> >> /Contents {content_id} 0 R >>"
        )
        objects[page_id - 1] = page.encode()

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, body in enumerate(objects[1:], 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    trailer = f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    output.extend(trailer.encode())
    response = HttpResponse(bytes(output), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def party_fields(party):
    return [party.display_name, party.external_identifier, party.email, party.notes]


def publishing_rows(track):
    rows = []
    links = track.work_links.select_related("work").prefetch_related(
        "contributors__party", "publishing_rights__party"
    )
    for link in links:
        for contributor in link.work.contributors.all():
            rows.append([
                link.work.title,
                "Contributor",
                contributor.party.display_name,
                contributor.role,
                contributor.share_percentage,
                *party_fields(contributor.party),
            ])
        for right in link.work.publishing_rights.all():
            rows.append([
                link.work.title,
                right.right_type.title(),
                right.party.display_name,
                right.right_type,
                right.ownership_percentage,
                *party_fields(right.party),
            ])
    return rows


PUBLISHING_HEADERS = (
    "Work title", "Record type", "Contributor / rights party", "Role / right type",
    "Publishing share %", "Government name", "External ID / IP name number",
    "Email address", "Party notes (society, address, publisher)",
)
