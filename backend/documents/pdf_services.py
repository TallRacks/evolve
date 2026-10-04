import re
from io import BytesIO
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from integrations.models import StorageProvider

from .models import Document
from .storage import DocumentStorageUnavailable, get_storage_backend

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _color(value, fallback):
    valid = value if isinstance(value, str) and HEX_COLOR.fullmatch(value) else fallback
    return colors.HexColor(valid)


def _paragraph(text, style):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def render_generated_document_pdf(document):
    if document.source_type != Document.SourceType.GENERATED or not document.rendered_content:
        raise ValidationError("Only generated documents can be exported as PDF.")

    branding = document.rendered_branding or {}
    primary = _color(branding.get("primary"), "#8A5A00")
    accent = _color(branding.get("accent"), "#A86B00")
    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=document.title,
        author=branding.get("brand_name") or "Evolve",
    )
    styles = getSampleStyleSheet()
    brand = ParagraphStyle(
        "EvolveBrand",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=accent,
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    title = ParagraphStyle(
        "EvolveTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=25,
        textColor=primary,
        spaceAfter=5,
    )
    meta = ParagraphStyle(
        "EvolveMeta",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=12,
    )
    heading = ParagraphStyle(
        "EvolveHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=primary,
        spaceBefore=9,
        spaceAfter=5,
    )
    body = ParagraphStyle(
        "EvolveBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#202124"),
        spaceAfter=7,
    )

    story = []
    logo_key = branding.get("logo_storage_key")
    provider_id = branding.get("logo_storage_provider_id")
    if logo_key and provider_id:
        try:
            provider = StorageProvider.objects.get(pk=provider_id)
            stored = get_storage_backend(provider).open_stream(logo_key)
            image_data = stored.body.read()
            stored.body.close()
            logo = Image(BytesIO(image_data), width=48 * mm, height=18 * mm, kind="proportional")
            logo.hAlign = "LEFT"
            story.extend([logo, Spacer(1, 4 * mm)])
        except (StorageProvider.DoesNotExist, DocumentStorageUnavailable, OSError, ValueError):
            pass
    header = branding.get("header_text") or branding.get("brand_name") or "Evolve document"
    story.append(_paragraph(header, brand))
    story.append(_paragraph(document.title, title))
    document_meta = f"{document.get_document_type_display()} · version {document.version_number}"
    story.append(_paragraph(document_meta, meta))
    story.append(Spacer(1, 3 * mm))
    blocks = re.split(r"\n\s*---\s*\n", document.rendered_content)
    for block in blocks:
        lines = [line.strip() for line in block.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            continue
        story.append(_paragraph(lines[0], heading))
        if len(lines) > 1:
            story.append(_paragraph("\n".join(lines[1:]), body))
        else:
            story.append(Spacer(1, 1 * mm))
    if branding.get("footer_text"):
        story.append(Spacer(1, 8 * mm))
        story.append(_paragraph(branding["footer_text"], meta))
    pdf.build(story)
    return buffer.getvalue()
