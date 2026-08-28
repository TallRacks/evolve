from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Document, DocumentLink, DocumentTemplate, DocumentTemplateSection
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
    document = Document.objects.create(
        organization=booking.organization,
        title=title,
        document_type=GENERATED_DOCUMENT_TYPES[template.document_type],
        rendered_content=content,
        template=template,
        template_version=template.version,
        uploaded_by=actor,
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
