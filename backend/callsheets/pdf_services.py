from io import BytesIO
from urllib.parse import quote
from xml.sax.saxutils import escape

from django.core.exceptions import ValidationError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from white_label.services import effective_branding

from .models import CallSheetVersion


def _paragraph(value, style):
    return Paragraph(escape(str(value or "")).replace("\n", "<br/>"), style)


def _map_link(label, address, style):
    """Create a clickable navigation link without allowing address text as markup."""
    target = quote(str(address or ""), safe="")
    google = f"https://www.google.com/maps/search/?api=1&query={target}"
    waze = f"https://waze.com/ul?q={target}&navigate=yes"
    return Paragraph(
        f"{escape(label)}: "
        f'<link href="{escape(google, {'"': '&quot;'})}">Google Maps</link> · '
        f'<link href="{escape(waze, {'"': '&quot;'})}">Waze</link>',
        style,
    )


def render_call_sheet_pdf(version):
    if version.status == CallSheetVersion.Status.CANCELLED:
        raise ValidationError("Cancelled Call Sheets cannot be exported.")

    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=version.title,
        author=version.call_sheet.organization.name,
    )
    styles = getSampleStyleSheet()
    branding = effective_branding(version.call_sheet.organization)
    primary = colors.HexColor(branding.get("primary", "#D6A84B"))
    accent = colors.HexColor(branding.get("accent", "#F0C96B"))
    heading = ParagraphStyle(
        "CallSheetHeading", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=primary,
        spaceBefore=9, spaceAfter=5,
    )
    body = ParagraphStyle(
        "CallSheetBody", parent=styles["BodyText"], fontSize=9.5,
        leading=13, textColor=colors.HexColor("#202124"), spaceAfter=4,
    )
    small = ParagraphStyle(
        "CallSheetSmall", parent=body, fontSize=8, leading=10,
        textColor=colors.HexColor("#5F6368"),
    )
    title_style = ParagraphStyle(
        "CallSheetTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=26,
        textColor=primary,
    )
    story = [
        _paragraph(branding.get("brand_name") or version.call_sheet.organization.name, small),
        _paragraph(version.title, title_style),
        _paragraph(
            f"{version.call_sheet.booking.reference} · Version "
            f"{version.version_number} · {version.status}",
            small,
        ),
        Spacer(1, 5 * mm),
    ]

    overview = [
        ["Artist", version.artist_name],
        ["Event", version.event_name],
        ["Date", version.event_date],
        ["Venue", version.venue_name or "Venue TBC"],
        ["Address", version.venue_address or "Address TBC"],
        ["Promoter", version.promoter_name or "Promoter TBC"],
        ["Point of contact", version.point_of_contact or "TBC"],
        ["Contact details", version.point_of_contact_details or "TBC"],
        ["On-site venue contact", version.onsite_contact or "TBC"],
        ["On-site contact details", version.onsite_contact_details or "TBC"],
        ["Call time", version.call_time or "TBC"],
        [
            "Performance",
            f"{version.performance_length_minutes} minutes"
            if version.performance_length_minutes
            else "TBC",
        ],
    ]
    table = Table(
        [[_paragraph(k, small), _paragraph(v, body)] for k, v in overview],
        colWidths=[34 * mm, 142 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(red=accent.red, green=accent.green, blue=accent.blue, alpha=0.22)),
        ("BOX", (0, 0), (-1, -1), 0.5, primary),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    sections = [
        (
            "Schedule",
            [
                f"{item.start_time or 'TBC'} · {item.title} · {item.location or ''}"
                for item in version.schedule_items.all()
            ],
        ),
        (
            "Team",
            [
                f"{item.call_time or 'TBC'} · {item.name_snapshot} · "
                f"{item.responsibility_snapshot or ''}"
                for item in version.team_entries.all()
            ],
        ),
        (
            "Contacts",
            [
                f"{item.name_snapshot} · {item.responsibility} · "
                f"{item.phone_snapshot or item.email_snapshot or ''}"
                for item in version.contact_entries.all()
            ],
        ),
        (
            "Travel",
            [
                f"{item.departure_location} → {item.arrival_location} · "
                f"{item.departure_datetime}"
                for item in version.travel_items.all()
            ],
        ),
        (
            "Accommodation",
            [
                f"{item.property_name} · {item.address or ''}"
                for item in version.accommodation_items.all()
            ],
        ),
        (
            "Venue and access",
            [
                version.venue_address,
                version.access_notes,
                version.loading_access,
                version.parking_notes,
                version.backstage_access,
                version.dressing_room_notes,
            ],
        ),
        (
            "Meet-up / pick-up point",
            [version.meet_up_point, version.meet_up_address, version.meet_up_url],
        ),
        (
            "Production",
            [
                version.production_contact,
                version.soundcheck_time,
                version.stage_notes,
                version.technical_notes,
                version.backline_notes,
                version.special_requirements,
            ],
        ),
        ("Hospitality", [version.catering_notes, version.dietary_notes, version.guest_notes]),
        (
            "Notes",
            [
                version.general_notes,
                version.artist_notes,
                version.team_notes,
                version.security_notes,
                version.emergency_notes,
            ],
        ),
    ]
    for title, values in sections:
        values = [str(value) for value in values if value]
        if not values:
            continue
        story.append(_paragraph(title, heading))
        story.extend(_paragraph(value, body) for value in values)

    navigation_addresses = []
    if version.venue_address:
        navigation_addresses.append(("Venue directions", version.venue_address))
    if version.meet_up_address:
        navigation_addresses.append(("Meet-up directions", version.meet_up_address))
    if navigation_addresses:
        story.append(_paragraph("Navigation", heading))
        story.extend(_map_link(label, address, body) for label, address in navigation_addresses)
    pdf.build(story)
    return buffer.getvalue()
