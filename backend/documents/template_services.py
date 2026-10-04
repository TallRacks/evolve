from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from organizations.permissions import user_has_organization_permission
from white_label.services import effective_branding

from .models import (
    Document,
    DocumentLink,
    DocumentTemplate,
    DocumentTemplateSection,
    OfficeDocumentContent,
)
from .template_validation import TOKEN, validate_template_text


def require_template_permission(actor, organization, permission):
    if organization is None:
        if not getattr(actor, "is_active", False) or not getattr(actor, "is_superuser", False):
            raise PermissionDenied("Platform templates require a platform superuser.")
        return
    if not user_has_organization_permission(actor, organization, permission):
        raise PermissionDenied("You do not have permission for this template.")


def booking_context(booking):
    venue = booking.venue
    address = ""
    if venue:
        address = ", ".join(
            filter(
                None,
                [
                    venue.address_line_1,
                    venue.address_line_2,
                    venue.city,
                    venue.province,
                    venue.postal_code,
                    venue.country,
                ],
            )
        )
    return {
        "organization.name": booking.organization.name,
        "artist.name": booking.artist.stage_name,
        "booking.reference": booking.reference,
        "booking.event_name": booking.title,
        "booking.date": booking.event_date.isoformat(),
        "booking.start": booking.event_start_datetime.isoformat()
        if booking.event_start_datetime
        else "",
        "booking.end": booking.event_end_datetime.isoformat() if booking.event_end_datetime else "",
        "venue.name": booking.venue_name_snapshot,
        "venue.address": address,
        "promoter.name": booking.promoter_name_snapshot,
        "promoter.email": "",
        "booking.city": booking.city_snapshot,
        "booking.currency": booking.currency,
        "booking.performance_fee": booking.performance_fee or "",
        "booking.deposit_amount": booking.deposit_amount or "",
        "booking.performance_type": booking.performance_type,
        "booking.event_type": booking.event_type,
    }


def render_template(template, context):
    sections, missing = [], set()
    for section in template.sections.filter(is_enabled=True).order_by("sequence"):
        validate_template_text(section.title)
        validate_template_text(section.body)

        def replace(match):
            value = context.get(match.group(1), "")
            if value in (None, ""):
                missing.add(match.group(1))
            return str(value or "")

        title = TOKEN.sub(replace, section.title).strip()
        body = TOKEN.sub(replace, section.body).strip()
        if title or body:
            sections.append("\n\n".join(filter(None, (title, body))))
    return "\n\n---\n\n".join(sections), sorted(missing)


@transaction.atomic
def create_template(*, actor, organization, data, request=None):
    require_template_permission(actor, organization, "document_template.manage")
    template = DocumentTemplate(organization=organization, created_by=actor, **data)
    if template.is_default:
        DocumentTemplate.objects.filter(organization=organization, document_type=template.document_type).update(is_default=False)
    template.full_clean()
    template.save()
    record_event(
        actor=actor,
        organization=organization,
        action="template.created",
        resource=template,
        description=f"Created document template {template.name}.",
        request=request,
    )
    return template


@transaction.atomic
def update_template(*, actor, template, data, request=None):
    require_template_permission(actor, template.organization, "document_template.manage")
    for field, value in data.items():
        if field not in {"organization", "created_by", "version", "status"}:
            setattr(template, field, value)
    template.version += 1
    template.full_clean()
    template.save()
    record_event(
        actor=actor,
        organization=template.organization,
        action="template.updated",
        resource=template,
        description=f"Updated document template {template.name}.",
        request=request,
    )
    return template


@transaction.atomic
def add_template_section(*, actor, template, data):
    require_template_permission(actor, template.organization, "document_template.manage")
    validate_template_text(data["title"])
    validate_template_text(data["body"])
    section = DocumentTemplateSection(template=template, **data)
    section.full_clean()
    section.save()
    DocumentTemplate.objects.filter(pk=template.pk).update(version=template.version + 1)
    return section


@transaction.atomic
def update_template_section(*, actor, section, data, request=None):
    require_template_permission(actor, section.template.organization, "document_template.manage")
    for field, value in data.items():
        setattr(section, field, value)
    section.full_clean()
    section.save()
    DocumentTemplate.objects.filter(pk=section.template_id).update(
        version=section.template.version + 1
    )
    record_event(
        actor=actor,
        organization=section.template.organization,
        action="template.section_updated",
        resource=section.template,
        description=f"Updated a section in document template {section.template.name}.",
        request=request,
    )
    return section


@transaction.atomic
def set_template_default(*, actor, template, request=None):
    require_template_permission(actor, template.organization, "document_template.manage")
    if template.status != DocumentTemplate.Status.ACTIVE:
        raise ValidationError("Only active templates can be made default.")
    DocumentTemplate.objects.filter(organization=template.organization, document_type=template.document_type).exclude(pk=template.pk).update(is_default=False)
    template.is_default = True
    template.version += 1
    template.save(update_fields=("is_default", "version", "updated_at"))
    record_event(actor=actor, organization=template.organization, action="template.default_set", resource=template, description=f"Set {template.name} as the default {template.document_type} template.", request=request)
    return template


@transaction.atomic
def set_template_status(*, actor, template, status, request=None):
    require_template_permission(actor, template.organization, "document_template.manage")
    DocumentTemplate.objects.filter(pk=template.pk).update(
        status=status, version=template.version + 1
    )
    template.refresh_from_db()
    record_event(
        actor=actor,
        organization=template.organization,
        action="template.activated"
        if status == DocumentTemplate.Status.ACTIVE
        else "template.deactivated",
        resource=template,
        description=f"Document template {template.name} is {status}.",
        request=request,
    )
    return template


@transaction.atomic
def duplicate_template(*, actor, template, organization, key, request=None):
    copy = create_template(
        actor=actor,
        organization=organization,
        data={
            "name": f"{template.name} copy",
            "key": key,
            "document_type": template.document_type,
            "description": template.description,
        },
        request=request,
    )
    for section in template.sections.all():
        DocumentTemplateSection.objects.create(
            template=copy,
            key=section.key,
            title=section.title,
            body=section.body,
            sequence=section.sequence,
            is_enabled=section.is_enabled,
        )
    return copy


GENERATED_DOCUMENT_TYPES = {
    DocumentTemplate.Type.BOOKING_CONFIRMATION: Document.Type.OTHER,
    DocumentTemplate.Type.BOOKING_BRIEF: Document.Type.OTHER,
    DocumentTemplate.Type.CALL_SHEET: Document.Type.CALL_SHEET,
    DocumentTemplate.Type.INVOICE: Document.Type.INVOICE,
    DocumentTemplate.Type.PERFORMANCE_AGREEMENT: Document.Type.CONTRACT,
    DocumentTemplate.Type.CONTRACT_SUMMARY: Document.Type.CONTRACT,
    DocumentTemplate.Type.INVOICE_COVER: Document.Type.INVOICE,
    DocumentTemplate.Type.TRAVEL_ITINERARY: Document.Type.TRAVEL,
    DocumentTemplate.Type.PRODUCTION_ADVANCE: Document.Type.OTHER,
    DocumentTemplate.Type.GENERAL: Document.Type.OTHER,
}


@transaction.atomic
def generate_booking_document(*, actor, template, booking, title, request=None):
    require_template_permission(actor, booking.organization, "document_template.view")
    if not user_has_organization_permission(actor, booking.organization, "document.manage"):
        raise PermissionDenied("You do not have permission to generate this document.")
    if template.status != DocumentTemplate.Status.ACTIVE or template.organization_id not in (
        None,
        booking.organization_id,
    ):
        raise ValidationError("Choose an active template available to this organization.")
    content, missing = render_template(template, booking_context(booking))
    if not content:
        raise ValidationError("The template did not produce document content.")
    branding = {**effective_branding(booking.organization), **(template.branding or {})}
    branding["primary"] = branding.get("primary") or branding.get("primary_color", "")
    branding["accent"] = branding.get("accent") or branding.get("accent_color", "")
    document = Document.objects.create(
        organization=booking.organization,
        title=title,
        document_type=GENERATED_DOCUMENT_TYPES[template.document_type],
        rendered_content=content,
        rendered_branding={
            key: branding.get(key, "")
            for key in (
                "brand_name",
                "logo_url",
                "primary",
                "accent",
                "text_primary",
                "header_text",
                "footer_text",
                "logo_storage_key",
                "logo_storage_provider_id",
                "logo_content_type",
            )
        },
        template=template,
        template_version=template.version,
        uploaded_by=actor,
    )
    OfficeDocumentContent.objects.create(
        document=document,
        format=OfficeDocumentContent.Format.DOCUMENT,
        content_json={
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": line}]}
                for line in content.splitlines()
                if line.strip()
            ]
            or [{"type": "paragraph", "content": []}],
        },
        last_edited_by=actor,
        last_edited_at=timezone.now(),
    )
    DocumentLink.objects.create(document=document, booking=booking)
    record_event(
        actor=actor,
        organization=booking.organization,
        action="document.generated",
        resource=document,
        description=f"Generated document from template {template.name} version {template.version}.",
        request=request,
    )
    return document, missing


@transaction.atomic
def bootstrap_templates(*, actor, organization, request=None):
    require_template_permission(actor, organization, "document_template.manage")
    starters = [
        ("Booking confirmation", "booking-confirmation", DocumentTemplate.Type.BOOKING_CONFIRMATION, DocumentTemplate.Category.BOOKINGS, [
            ("summary", "Booking summary", "Organization: {{ organization.name }}\nArtist: {{ artist.name }}\nEvent: {{ booking.event_name }}\nReference: {{ booking.reference }}"),
            ("schedule", "Schedule", "Date: {{ booking.date }}\nStart: {{ booking.start }}\nEnd: {{ booking.end }}"),
            ("venue", "Venue", "{{ venue.name }}\n{{ venue.address }}"),
        ]),
        ("Booking brief", "booking-brief", DocumentTemplate.Type.BOOKING_BRIEF, DocumentTemplate.Category.BOOKINGS, [
            ("overview", "Booking overview", "Artist: {{ artist.name }}\nEvent: {{ booking.event_name }}\nPromoter: {{ promoter.name }}"),
            ("location", "Location", "Venue: {{ venue.name }}\nAddress: {{ venue.address }}"),
        ]),
        ("Invoice", "invoice", DocumentTemplate.Type.INVOICE, DocumentTemplate.Category.MANAGEMENT, [
            ("header", "Invoice", "{{ organization.name }}\nInvoice for {{ artist.name }}"),
            ("booking", "Booking", "Reference: {{ booking.reference }}\nEvent: {{ booking.event_name }}\nDate: {{ booking.date }}"),
            ("amounts", "Amounts", "Currency: {{ booking.currency }}\nPerformance fee: {{ booking.performance_fee }}\nDeposit: {{ booking.deposit_amount }}"),
        ]),
        ("Invoice cover", "invoice-cover", DocumentTemplate.Type.INVOICE_COVER, DocumentTemplate.Category.MANAGEMENT, [
            ("summary", "Invoice summary", "{{ organization.name }}\n{{ booking.reference }} / {{ booking.event_name }}"),
            ("billing", "Billing", "Artist: {{ artist.name }}\nPromoter: {{ promoter.name }}\nCurrency: {{ booking.currency }}"),
        ]),
        ("Call sheet", "call-sheet", DocumentTemplate.Type.CALL_SHEET, DocumentTemplate.Category.LIVE, [
            ("show", "Show details", "{{ booking.event_name }}\n{{ booking.date }}\n{{ venue.name }}"),
            ("timing", "Timing", "Start: {{ booking.start }}\nEnd: {{ booking.end }}"),
            ("contacts", "Operational notes", "Promoter: {{ promoter.name }}"),
        ]),
        ("Artist Booking & Performance Agreement", "artist-performance-agreement", DocumentTemplate.Type.PERFORMANCE_AGREEMENT, DocumentTemplate.Category.BOOKINGS, [
            ("parties", "Parties", "Organiser: {{ promoter.name }}\nArtist Management: {{ organization.name }}\nPerforming Artist: {{ artist.name }}\n\nThe parties agree to the following booking and performance terms."),
            ("event-details", "Event details", "Event Name: {{ booking.event_name }}\nDate: {{ booking.date }}\nLocation: {{ venue.name }}\nVenue Address: {{ venue.address }}\nPerformance Type: {{ booking.performance_type }}\nEvent Type: {{ booking.event_type }}\nPerformance duration and sound-check timing: to be confirmed in the booking operations record.\nRider requirements: Annexure A forms part of this Agreement."),
            ("advertising-media", "Advertising & media", "All event artwork must be approved by the Artist and Artist Management.\nThe Organiser is responsible for applicable music licences.\nMedia interviews shall be coordinated through Artist Management.\nUse of the Artist’s name, image, logo, or trademarks requires prior approval.\nThe Artist is not obligated to post event marketing."),
            ("recording", "Recording", "The Organiser may not record the performance for commercial use without prior written consent from Artist Management.\nLimited recording of up to two minutes may be permitted for news or archive purposes with prior approval.\nThe Artist’s crew may record the event for personal use."),
            ("cancellation", "Cancellation policy", "If the Organiser cancels more than 30 days before the performance date, the Artist retains deposits.\nIf the Organiser cancels less than 30 days before the performance date, the full fee is payable.\nForce majeure obligations are excused and the parties shall seek to reschedule within three months.\nIf attendance is below 100, the Artist may refuse to perform and the full fee is forfeited by the Organiser."),
            ("indemnity", "Indemnity", "The Organiser indemnifies the Artist and team against claims, damages, or losses arising from the event."),
            ("breach", "Breach and termination", "Either party may terminate this Agreement by written notice if the other party commits a material breach and fails to remedy it within 14 days of receiving written notice specifying the breach. Termination is without prejudice to accrued rights and remedies."),
            ("jurisdiction", "Jurisdiction & dispute resolution", "This Agreement is governed by the laws of the Republic of South Africa. The parties shall first explore mediation and arbitration through the Arbitration Foundation of Southern Africa in Johannesburg before resorting to litigation."),
            ("warranties", "Warranties", "Both parties warrant that they are legally entitled to enter into this Agreement. Intellectual property rights in the Artist’s performance, including music, lyrics, compositions, and creative content, remain the sole and exclusive property of the Artist."),
            ("signatures", "Signatures", "Signed by Organiser: {{ promoter.name }}\n\nSignature: ______________________________\nDate: __________________\n\nSigned by Artist Management: {{ organization.name }}\n\nSignature: ______________________________\nDate: __________________"),
            ("annexure-a", "Annexure A — Hospitality and technical rider", "This Annexure forms part of the Agreement.\n\nRider provisions\n2 Hennessy VSOP\n2 Don Julio Tequila\n12 Tonic Water, 12 Lemonade, 12 Monster, 12 Water\n2 Hubbly\n1x Food Platter\n\nDressing room requirements\nMinimum size: 5m x 5m\nFurniture for 8 people\nFood and drinks set up prior to arrival\n1 venue security at entrance\n\nTechnical & hospitality rider\nAdequate security provided\nNo unauthorised persons on stage\nStage, sound, and lighting per the Artist’s technical rider\nIndoor facility provided in case of inclement weather\nCertified roofing and protection against adverse weather\n\nSecurity\nSecurity escort for Artist to/from stage\nVIP and backstage passes provided\nDressing room photos to be shared prior to the event."),
        ]),
        ("Hospitality Rider", "hospitality-rider", DocumentTemplate.Type.GENERAL, DocumentTemplate.Category.LIVE, [
            ("provisions", "Rider provisions", "2 Hennessy VSOP\n2 Don Julio Tequila\n12 Tonic Water, 12 Lemonade, 12 Monster, 12 Water\n2 Hubbly\n1x Food Platter"),
            ("dressing-room", "Dressing room requirements", "Minimum size: 5m x 5m\nFurniture for 8 people\nFood and drinks set up prior to arrival\n1 venue security at entrance"),
            ("technical-hospitality", "Technical & hospitality rider", "Adequate security provided\nNo unauthorised persons on stage\nStage, sound, and lighting per Artist’s technical rider\nIndoor facility provided in case of inclement weather\nCertified roofing and protection against adverse weather"),
            ("security", "Security", "Security escort for Artist to/from stage\nVIP and backstage passes provided\nDressing room photos to be shared prior to the event."),
        ]),
    ]
    result = []
    for name, key, document_type, category, sections in starters:
        template, created = DocumentTemplate.objects.get_or_create(organization=organization, key=key, defaults={"name": name, "document_type": document_type, "category": category, "description": f"Starter {name.lower()} template.", "status": DocumentTemplate.Status.ACTIVE, "is_default": document_type == DocumentTemplate.Type.CALL_SHEET, "created_by": actor})
        if created:
            for sequence, (section_key, title, body) in enumerate(sections, 1):
                DocumentTemplateSection.objects.create(template=template, key=section_key, title=title, body=body, sequence=sequence)
            record_event(actor=actor, organization=organization, action="template.created", resource=template, description=f"Created starter template {template.name}.", request=request)
        result.append(template)
    return result
