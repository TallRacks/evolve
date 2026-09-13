"""Deterministic Office documents generated from authoritative domain records."""

from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from organizations.permissions import user_has_organization_permission

from .models import Document, DocumentLink, OfficeDocumentContent
from .office_services import create_office_document, validate_content

BOOKING_GENERATORS = {
    "booking-brief": (
        "Booking Brief",
        Document.Type.OTHER,
        OfficeDocumentContent.Format.DOCUMENT,
        True,
    ),
    "show-day-brief": (
        "Show-Day Brief",
        Document.Type.OTHER,
        OfficeDocumentContent.Format.DOCUMENT,
        True,
    ),
    "production-notes": (
        "Production Notes",
        Document.Type.OTHER,
        OfficeDocumentContent.Format.NOTE,
        True,
    ),
    "meeting-note": ("Meeting Note", Document.Type.OTHER, OfficeDocumentContent.Format.NOTE, False),
}
RELEASE_GENERATORS = {
    "release-one-sheet": (
        "Release One-Sheet",
        Document.Type.MUSIC,
        OfficeDocumentContent.Format.DOCUMENT,
    ),
    "metadata-sheet": ("Metadata Sheet", Document.Type.MUSIC, OfficeDocumentContent.Format.SHEET),
    "credits-sheet": ("Credits Sheet", Document.Type.MUSIC, OfficeDocumentContent.Format.SHEET),
    "campaign-brief": (
        "Campaign Brief",
        Document.Type.MUSIC,
        OfficeDocumentContent.Format.DOCUMENT,
    ),
    "release-checklist": (
        "Release Checklist",
        Document.Type.MUSIC,
        OfficeDocumentContent.Format.CHECKLIST,
    ),
}


def _text(value):
    return str(value) if value not in (None, "") else "Not provided"


def _node(kind, text):
    return {"type": kind, "content": [{"type": "text", "text": _text(text)}]}


def _document(title, sections):
    content = [
        {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": title}]}
    ]
    for heading, value in sections:
        content.append(
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": heading}],
            }
        )
        content.append(_node("paragraph", value))
    return {"type": "doc", "content": content}


def _checklist(title, groups):
    items = []
    for group in groups:
        items.append(_node("heading", group))
        items.append(
            {
                "type": "checklist",
                "content": [
                    {
                        "type": "check_item",
                        "attrs": {"checked": False},
                        "content": [{"type": "text", "text": group}],
                    }
                ],
            }
        )
    return {
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": title}]}
        ]
        + items,
    }


def _sheet(columns, rows):
    return {"type": "sheet", "columns": columns, "rows": rows}


def _booking_sections(booking, include_operations=True):
    sections = [
        ("Booking Reference", booking.reference),
        ("Artist", booking.artist.stage_name),
        ("Event", booking.title),
        ("Date", booking.event_date),
        ("Time", booking.event_start_datetime),
        ("Venue", booking.venue_name_snapshot or getattr(booking.venue, "name", None)),
        ("Promoter", booking.promoter_name_snapshot or getattr(booking.promoter, "name", None)),
        ("Priority / Status", f"{booking.priority} / {booking.status}"),
    ]
    if include_operations:
        sections.extend(
            [
                (
                    "Readiness",
                    getattr(getattr(booking, "production_advance", None), "status", None),
                ),
                (
                    "Team",
                    ", ".join(
                        a.membership.user.get_full_name() or a.membership.user.email
                        for a in booking.team_assignments.filter(is_active=True).select_related(
                            "membership__user"
                        )
                    )
                    or "Not provided",
                ),
                (
                    "Contacts",
                    ", ".join(
                        a.snapshot_name for a in booking.contact_assignments.filter(is_active=True)
                    )
                    or "Not provided",
                ),
                (
                    "Production",
                    "Linked production advance"
                    if getattr(booking, "production_advance", None)
                    else "Needs Attention",
                ),
                (
                    "Travel",
                    "Linked travel itinerary"
                    if getattr(booking, "travel_itinerary", None)
                    else "Needs Attention",
                ),
                (
                    "Call Sheet",
                    "Linked call sheet"
                    if getattr(booking, "call_sheet", None)
                    else "Needs Attention",
                ),
                (
                    "Open Tasks",
                    str(booking.tasks.exclude(status__in=("done", "cancelled")).count()),
                ),
            ]
        )
    return sections


def _release_sections(release):
    return [
        ("Artist", release.primary_artist.stage_name),
        ("Release", release.title),
        ("Release Type", release.get_release_type_display()),
        ("Release Date", release.planned_release_date),
        ("Status", release.status),
        ("Artwork Reference", release.artwork_url or "Needs Attention"),
        (
            "Track List",
            ", ".join(item.track.title for item in release.track_placements.select_related("track"))
            or "Needs Attention",
        ),
        (
            "Credits",
            str(release.credits.count()) if release.credits.exists() else "Needs Attention",
        ),
        ("Campaign", ", ".join(c.name for c in release.campaigns.all()) or "Not yet created"),
        ("Links", ", ".join(link.url for link in release.links.all()) or "Needs Attention"),
    ]


def _generator_description(key):
    return f"[evolve-generator:{key}] Generated Office content. Refresh from source explicitly."


def _find_existing(organization, key, relation, source_id):
    filters = {
        "organization": organization,
        "status": Document.Status.ACTIVE,
        "description__startswith": f"[evolve-generator:{key}]",
        "office_content__isnull": False,
        f"links__{relation}_id": source_id,
    }
    return Document.objects.select_for_update().filter(**filters).order_by("-updated_at").first()


def _create(
    actor,
    source,
    key,
    title,
    document_type,
    fmt,
    content,
    relation,
    request=None,
    idempotent=True,
    extra_links=(),
):
    if not user_has_organization_permission(actor, source.organization, "document.manage"):
        raise PermissionError("You do not have permission to create Office documents.")
    with transaction.atomic():
        existing = (
            _find_existing(source.organization, key, relation, source.pk) if idempotent else None
        )
        if existing:
            return existing, True
        document = create_office_document(
            actor=actor,
            organization=source.organization,
            title=f"{title} — {source}",
            document_type=document_type,
            format=fmt,
            visibility=Document.Visibility.ORGANIZATION,
            request=request,
        )
        document.description = _generator_description(key)
        document.save(update_fields=("description", "updated_at"))
        office_content = document.office_content
        office_content.content_json = content
        office_content.save(update_fields=("content_json", "updated_at"))
        DocumentLink.objects.create(document=document, **{relation: source})
        for field, value in extra_links:
            DocumentLink.objects.create(document=document, **{field: value})
        record_event(
            actor=actor,
            organization=source.organization,
            action=f"office.{key.replace('-', '_')}_created",
            resource=document,
            description=f"Created {title} from source record.",
            request=request,
        )
        return document, False


@transaction.atomic
def generate_booking_office(*, actor, booking, generator, request=None):
    if generator not in BOOKING_GENERATORS:
        raise ValueError("Unsupported Booking Office generator.")
    if not user_has_organization_permission(actor, booking.organization, "booking.view"):
        raise PermissionError("You do not have permission to view this Booking.")
    title, doc_type, fmt, idempotent = BOOKING_GENERATORS[generator]
    if generator == "show-day-brief":
        content = _document(title, _booking_sections(booking) + [("Generated", timezone.now())])
    elif generator == "production-notes":
        content = _document(
            title,
            _booking_sections(booking, False)
            + [
                (
                    "Production context",
                    getattr(getattr(booking, "production_advance", None), "status", None),
                )
            ],
        )
    elif generator == "meeting-note":
        content = _document(title, _booking_sections(booking, False))
    else:
        content = _document(title, _booking_sections(booking))
    validate_content(content)
    return _create(
        actor,
        booking,
        generator,
        title,
        doc_type,
        fmt,
        content,
        "booking",
        request=request,
        idempotent=idempotent,
        extra_links=(("artist", booking.artist),),
    )


@transaction.atomic
def generate_release_office(*, actor, release, generator, request=None):
    if generator not in RELEASE_GENERATORS:
        raise ValueError("Unsupported Release Office generator.")
    if not user_has_organization_permission(actor, release.organization, "music.view"):
        raise PermissionError("You do not have permission to view this Release.")
    title, doc_type, fmt = RELEASE_GENERATORS[generator]
    if generator == "release-one-sheet":
        content = _document(title, _release_sections(release))
    elif generator == "campaign-brief":
        content = _document(
            title,
            _release_sections(release)
            + [("Rollout", "Review current rollout milestones in the linked campaign.")],
        )
    elif generator == "release-checklist":
        content = _checklist(
            title,
            [
                "Tracks",
                "Metadata",
                "Identifiers",
                "Credits",
                "Rights",
                "Master",
                "Artwork",
                "Distribution",
                "Campaign",
                "Release Day",
            ],
        )
    elif generator == "metadata-sheet":
        columns = [
            {"id": name.lower().replace(" ", "_"), "name": name, "type": "TEXT"}
            for name in (
                "Track",
                "Version",
                "Artist",
                "ISRC",
                "Explicit",
                "Genre",
                "Language",
                "Writers",
                "Producers",
                "Release",
                "Track Sequence",
            )
        ]
        rows = []
        for placement in release.track_placements.select_related("track", "track__primary_artist"):
            track = placement.track
            rows.append(
                {
                    "id": str(track.id),
                    "cells": {
                        "track": track.title,
                        "version": track.version_title,
                        "artist": track.primary_artist.stage_name,
                        "isrc": track.isrc,
                        "explicit": str(track.explicit_content),
                        "genre": track.genre,
                        "language": track.language,
                        "writers": ", ".join(
                            c.name for c in track.credits.filter(credit_role="songwriter")
                        ),
                        "producers": ", ".join(
                            c.name for c in track.credits.filter(credit_role="producer")
                        ),
                        "release": release.title,
                        "track_sequence": str(placement.sequence),
                    },
                }
            )
        content = _sheet(columns, rows)
    else:
        columns = [
            {"id": "track", "name": "Track", "type": "TEXT"},
            {"id": "name", "name": "Contributor", "type": "TEXT"},
            {"id": "role", "name": "Role", "type": "TEXT"},
        ]
        rows = [
            {
                "id": str(c.id),
                "cells": {
                    "track": c.track.title if c.track else release.title,
                    "name": c.name,
                    "role": c.get_credit_role_display(),
                },
            }
            for c in release.credits.select_related("track")
        ]
        content = _sheet(columns, rows)
    validate_content(content)
    return _create(
        actor,
        release,
        generator,
        title,
        doc_type,
        fmt,
        content,
        "release",
        request=request,
        extra_links=(("artist", release.primary_artist),),
    )
