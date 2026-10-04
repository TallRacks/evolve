from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from artists.models import Artist
from bookings.models import Booking
from contacts.models import Contact
from contacts.services import create_contact
from bookings.services import create_booking, transition_booking, update_booking
from promoters.models import Promoter
from promoters.services import create_promoter, update_promoter
from venues.models import Venue
from venues.services import create_venue, update_venue
from music.import_services import import_release_tracker

from integrations.services import resolve_secret
from audit.services import record_event
from organizations.permissions import user_has_organization_permission
from .models import Tracker, TrackerSyncEvent
def require_tracker_permission(actor, organization):
    if not user_has_organization_permission(actor, organization, "calendar.manage"):
        raise ValidationError("You do not have permission to manage spreadsheet trackers.")
@transaction.atomic
def request_sync(*, actor, tracker, direction, request=None):
    require_tracker_permission(actor, tracker.organization)
    if tracker.google_connector.connection_status != "healthy":
        raise ValidationError("Test and activate the Google Sheets connector before syncing.")
    if tracker.kind not in {Tracker.Kind.BOOKINGS, Tracker.Kind.RELEASES}:
        raise ValidationError("Live Sheets sync is currently available for booking and release trackers.")
    event = TrackerSyncEvent.objects.create(tracker=tracker, direction=direction, status="running", requested_by=actor)
    try:
        if tracker.kind == Tracker.Kind.RELEASES:
            if direction != "import":
                raise ValidationError("Release trackers currently support import from Google Sheets; export will be added after the release schema is confirmed.")
            created, updated, skipped, message = _import_release_rows(tracker, actor, request)
        elif direction == "import":
            created, updated, skipped, message = _import_booking_rows(tracker, actor, request)
        else:
            created, updated, skipped, message = _export_booking_rows(tracker)
        event.status = "completed"
        event.rows_created, event.rows_updated, event.rows_skipped = created, updated, skipped
        event.message = message
        tracker.last_sync_status, tracker.last_sync_message = "completed", message
    except ValidationError as error:
        event.status, event.message = "failed", str(error)
        tracker.last_sync_status, tracker.last_sync_message = "failed", str(error)
        event.save(update_fields=("status", "message", "updated_at"))
        tracker.save(update_fields=("last_sync_status", "last_sync_message", "updated_at"))
        raise
    event.save(update_fields=("status", "rows_created", "rows_updated", "rows_skipped", "message", "updated_at"))
    tracker.last_synced_at = timezone.now()
    tracker.save(update_fields=("last_sync_status", "last_sync_message", "last_synced_at", "updated_at"))
    record_event(actor=actor, organization=tracker.organization, action=f"tracker.sync_{direction}", resource=tracker, description=f"Completed {direction} sync for {tracker.name}.", request=request)
    return event


BOOKING_TRACKER_FIELDS = (
    {"key": "reference", "header": "Booking Reference", "type": "text", "source": "reference"},
    {"key": "title", "header": "Event Name", "type": "text", "source": "title"},
    {"key": "artist", "header": "Artist", "type": "text", "source": "artist.stage_name"},
    {"key": "status", "header": "Status", "type": "choice", "source": "status"},
    {"key": "priority", "header": "Priority", "type": "choice", "source": "priority"},
    {"key": "performance_type", "header": "Performance Type", "type": "choice", "source": "performance_type"},
    {"key": "event_type", "header": "Event Type", "type": "choice", "source": "event_type"},
    {"key": "event_date", "header": "Event Date", "type": "date", "source": "event_date"},
    {"key": "event_start_datetime", "header": "Performance Start", "type": "datetime", "source": "event_start_datetime"},
    {"key": "event_end_datetime", "header": "Performance End", "type": "datetime", "source": "event_end_datetime"},
    {"key": "timezone", "header": "Timezone", "type": "text", "source": "timezone"},
    {"key": "venue_name", "header": "Venue", "type": "text", "source": "venue_name_snapshot"},
    {"key": "venue_address", "header": "Venue Address", "type": "text", "source": "venue.address"},
    {"key": "city", "header": "City", "type": "text", "source": "city_snapshot"},
    {"key": "country", "header": "Country", "type": "text", "source": "country_snapshot"},
    {"key": "promoter_name", "header": "Promoter", "type": "text", "source": "promoter_name_snapshot"},
    {"key": "promoter_contact", "header": "Promoter Contact", "type": "text", "source": "promoter.primary_contact"},
    {"key": "promoter_email", "header": "Promoter Email", "type": "text", "source": "promoter.email"},
    {"key": "promoter_phone", "header": "Promoter Phone", "type": "text", "source": "promoter.phone"},
    {"key": "venue_contact_email", "header": "Venue Email", "type": "text", "source": "venue.public_email"},
    {"key": "venue_contact_phone", "header": "Venue Phone", "type": "text", "source": "venue.public_phone"},
    {"key": "currency", "header": "Currency", "type": "text", "source": "currency"},
    {"key": "performance_fee", "header": "Performance Fee", "type": "money", "source": "performance_fee"},
    {"key": "deposit_amount", "header": "Deposit Amount", "type": "money", "source": "deposit_amount"},
    {"key": "deposit_due_date", "header": "Deposit Due Date", "type": "date", "source": "deposit_due_date"},
    {"key": "balance_due_date", "header": "Balance Due Date", "type": "date", "source": "balance_due_date"},
    {"key": "assigned_team", "header": "Assigned Team", "type": "text", "source": "team_assignments"},
    {"key": "notes", "header": "Operational Notes", "type": "text", "source": "internal_notes"},
    {"key": "updated_at", "header": "Last Updated", "type": "datetime", "source": "updated_at"},
)


RELEASE_TRACKER_FIELDS = (
    {"key": "release_title", "header": "Release Title", "type": "text"},
    {"key": "release_date", "header": "Release Date", "type": "date"},
    {"key": "artist", "header": "Artist", "type": "text"},
    {"key": "track_title", "header": "Track Title", "type": "text"},
    {"key": "isrc", "header": "ISRC", "type": "text"},
    {"key": "contributor", "header": "Contributor", "type": "text"},
    {"key": "split", "header": "Split %", "type": "number"},
    {"key": "master_split", "header": "Master Share %", "type": "number"},
    {"key": "publisher", "header": "Publisher", "type": "text"},
)

def tracker_fields(tracker):
    if tracker.kind == Tracker.Kind.BOOKINGS:
        return [field for field in BOOKING_TRACKER_FIELDS if field["key"] in SAFE_BOOKING_KEYS]
    if tracker.kind == Tracker.Kind.RELEASES:
        return list(RELEASE_TRACKER_FIELDS)
    return []


def _slug(value):
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "column"


def _header_key(value):
    return " ".join(str(value).strip().lower().split())


_VENUE_ADJACENT_HEADERS = {
    "currency",
    "performance fee",
    "deposit amount",
    "deposit due date",
    "balance due date",
}


def _ordered_tracker_headers(columns, additions):
    """Add canonical fields without disturbing the user's existing layout."""
    result = list(columns)
    existing = {_header_key(column) for column in result}
    additions = [column for column in additions if _header_key(column) not in existing]
    adjacent = [column for column in additions if _header_key(column) in _VENUE_ADJACENT_HEADERS]
    remainder = [column for column in additions if _header_key(column) not in _VENUE_ADJACENT_HEADERS]
    venue_index = next((index for index, column in enumerate(result) if _header_key(column) == "venue"), None)
    if venue_index is None:
        return result + additions
    return result[: venue_index + 1] + adjacent + result[venue_index + 1 :] + remainder


def reconcile_schema(*, tracker, columns, apply_headers=False, actor=None, request=None):
    if tracker.kind not in {Tracker.Kind.BOOKINGS, Tracker.Kind.RELEASES}:
        raise ValidationError("Schema reconciliation is currently available for booking and release trackers.")
    if not isinstance(columns, list) or any(not isinstance(column, str) or not column.strip() for column in columns):
        raise ValidationError("columns must be a non-empty list of header strings.")
    columns = [column.strip() for column in columns]
    canonical = tracker_fields(tracker)
    configured = tracker.field_mapping if isinstance(tracker.field_mapping, dict) else {}
    header_overrides = configured.get("headers", {}) if isinstance(configured.get("headers", {}), dict) else {}
    expected = [{**field, "header": header_overrides.get(field["key"], field["header"])} for field in canonical]
    existing = {_header_key(column): column for column in columns}
    missing = [field for field in expected if _header_key(field["header"]) not in existing]
    known = {_header_key(field["header"]) for field in expected}
    custom = []
    seen_custom = set()
    for column in columns:
        key = _slug(column)
        if _header_key(column) not in known and key not in seen_custom:
            custom.append({"key": f"custom.{key}", "header": column, "type": "text", "status": "unmapped"})
            seen_custom.add(key)
    desired_columns = _ordered_tracker_headers(columns, [field["header"] for field in missing])
    state = {
        "version": 1,
        "columns": desired_columns,
        "canonical_fields": expected,
        "missing_columns": missing,
        "custom_columns": custom,
        "reconciled_at": timezone.now().isoformat(),
    }
    if apply_headers and missing:
        _update_sheet_headers(tracker, desired_columns)
    tracker.schema_state = state
    tracker.save(update_fields=("schema_state", "updated_at"))
    if actor:
        record_event(actor=actor, organization=tracker.organization, action="tracker.schema_reconciled", resource=tracker, description=f"Reconciled booking tracker schema for {tracker.name}.", request=request)
    return state



SAFE_BOOKING_KEYS = {
    "reference", "title", "artist", "status", "priority", "performance_type",
    "event_type", "event_date", "event_start_datetime", "event_end_datetime",
    "timezone", "venue_name", "venue_address", "city", "country", "promoter_name",
    "promoter_email", "promoter_phone", "venue_contact_email", "venue_contact_phone",
    "currency", "performance_fee", "deposit_amount", "deposit_due_date", "balance_due_date",
}


def _google_sheets_error(error, action):
    raw = error.read().decode("utf-8", errors="replace")
    try:
        detail = json.loads(raw).get("error", {}).get("message", "")
    except json.JSONDecodeError:
        detail = ""
    if "must not be an Office file" in detail:
        return "Google Sheets cannot sync this Office/Excel file. Open it in Google Sheets, choose File > Save as Google Sheets, then edit this tracker to use the new Google Sheet ID."
    return f"Google Sheets {action} failed ({error.code}). Check the spreadsheet ID, worksheet name, and sharing access."

def _sheet_values(tracker):
    token = _google_access_token(tracker)
    encoded_range = urllib.parse.quote(f"'{tracker.worksheet_name}'!A:AZ", safe="")
    request = urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{urllib.parse.quote(tracker.spreadsheet_id, safe='')}/values/{encoded_range}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode()).get("values", [])
    except urllib.error.HTTPError as error:
        raise ValidationError(_google_sheets_error(error, "read")) from error
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValidationError("Google Sheets read failed. Google was unreachable or returned invalid data.") from error


def _write_sheet_values(tracker, values):
    token = _google_access_token(tracker)
    body = json.dumps({"valueInputOption": "USER_ENTERED", "data": [{"range": f"'{tracker.worksheet_name}'!A1", "majorDimension": "ROWS", "values": values}]}).encode()
    request = urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{urllib.parse.quote(tracker.spreadsheet_id, safe='')}/values:batchUpdate",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25):
            return
    except urllib.error.HTTPError as error:
        raise ValidationError(_google_sheets_error(error, "write")) from error
    except urllib.error.URLError as error:
        raise ValidationError("Google Sheets write failed because Google was unreachable.") from error


def _clear_trailing_sheet_values(tracker, first_row, last_row):
    if first_row > last_row:
        return
    token = _google_access_token(tracker)
    sheet_range = f"'{tracker.worksheet_name}'!A{first_row}:AZ{last_row}"
    url = "https://sheets.googleapis.com/v4/spreadsheets/" + urllib.parse.quote(tracker.spreadsheet_id, safe="") + "/values/" + urllib.parse.quote(sheet_range, safe="") + ":clear"
    request = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25):
            return
    except urllib.error.HTTPError as error:
        raise ValidationError(_google_sheets_error(error, "clear stale rows")) from error
    except urllib.error.URLError as error:
        raise ValidationError("Google Sheets cleanup failed because Google was unreachable.") from error


def _safe_fields(tracker):
    return [field for field in tracker_fields(tracker) if field["key"] in SAFE_BOOKING_KEYS]


def _booking_values(booking):
    venue = booking.venue
    if not venue and booking.venue_name_snapshot:
        venue = Venue.objects.filter(
            organization=booking.organization,
            name__iexact=booking.venue_name_snapshot.strip(),
        ).first()
    promoter = booking.promoter
    if not promoter and booking.promoter_name_snapshot:
        promoter = Promoter.objects.filter(
            organization=booking.organization,
            name__iexact=booking.promoter_name_snapshot.strip(),
        ).first()
    venue_address = ""
    if venue:
        venue_address = ", ".join(
            value for value in (
                venue.address_line_1,
                venue.address_line_2,
                venue.city,
                venue.province,
                venue.postal_code,
                venue.country,
            ) if value
        )
    return {
        "reference": booking.reference,
        "title": booking.title,
        "artist": booking.artist.stage_name,
        "status": booking.status,
        "priority": booking.priority,
        "performance_type": booking.performance_type,
        "event_type": booking.event_type,
        "event_date": booking.event_date.isoformat(),
        "event_start_datetime": booking.event_start_datetime.isoformat() if booking.event_start_datetime else "",
        "event_end_datetime": booking.event_end_datetime.isoformat() if booking.event_end_datetime else "",
        "timezone": booking.timezone,
        "venue_name": (venue.name if venue else "") or booking.venue_name_snapshot,
        "venue_address": venue_address,
        "city": (venue.city if venue else "") or booking.city_snapshot,
        "country": (venue.country if venue else "") or booking.country_snapshot,
        "promoter_name": (promoter.name if promoter else "") or booking.promoter_name_snapshot,
        "promoter_email": promoter.email if promoter else "",
        "promoter_phone": promoter.phone if promoter else "",
        "venue_contact_email": venue.public_email if venue else "",
        "venue_contact_phone": venue.public_phone if venue else "",
        "currency": booking.currency,
        "performance_fee": str(booking.performance_fee) if booking.performance_fee is not None else "",
        "deposit_amount": str(booking.deposit_amount) if booking.deposit_amount is not None else "",
        "deposit_due_date": booking.deposit_due_date.isoformat() if booking.deposit_due_date else "",
        "balance_due_date": booking.balance_due_date.isoformat() if booking.balance_due_date else "",
        "custom_fields": booking.custom_fields or {},
    }


def _apply_export_format(tracker, existing_row_count, output_row_count, column_count):
    if output_row_count <= existing_row_count or existing_row_count < 2:
        return
    token = _google_access_token(tracker)
    metadata_url = "https://sheets.googleapis.com/v4/spreadsheets/" + urllib.parse.quote(tracker.spreadsheet_id, safe="") + "?fields=sheets(properties(sheetId,title))"
    metadata_request = urllib.request.Request(metadata_url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(metadata_request, timeout=20) as response:
            sheets = json.loads(response.read().decode()).get("sheets", [])
        sheet_id = next(sheet["properties"]["sheetId"] for sheet in sheets if sheet["properties"].get("title") == tracker.worksheet_name)
        body = json.dumps({"requests": [{"copyPaste": {"source": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": column_count}, "destination": {"sheetId": sheet_id, "startRowIndex": existing_row_count, "endRowIndex": output_row_count, "startColumnIndex": 0, "endColumnIndex": column_count}, "pasteType": "PASTE_FORMAT"}}]}).encode()
        request = urllib.request.Request("https://sheets.googleapis.com/v4/spreadsheets/" + urllib.parse.quote(tracker.spreadsheet_id, safe="") + ":batchUpdate", data=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=20):
            return
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, StopIteration):
        return


def _export_booking_rows(tracker):
    existing = _sheet_values(tracker)
    fields = _safe_fields(tracker)
    canonical_headers = [field["header"] for field in fields]
    headers = existing[0] if existing else canonical_headers
    header_keys = {_header_key(value): index for index, value in enumerate(headers)}
    missing_headers = [header for header in canonical_headers if _header_key(header) not in header_keys]
    ordered_headers = _ordered_tracker_headers(headers, missing_headers)
    if ordered_headers != headers:
        old_indexes = {_header_key(header): index for index, header in enumerate(headers)}
        existing = [[
            row[old_indexes[_header_key(header)]] if _header_key(header) in old_indexes and old_indexes[_header_key(header)] < len(row) else ""
            for header in ordered_headers
        ] for row in existing]
        headers = ordered_headers
    header_keys = {_header_key(value): index for index, value in enumerate(headers)}
    reference_index = header_keys.get(_header_key("Booking Reference"))
    date_index = header_keys.get(_header_key("Event Date"))
    promoter_index = header_keys.get(_header_key("Promoter"))
    venue_index = header_keys.get(_header_key("Venue"))
    event_type_index = header_keys.get(_header_key("Event Type"))
    title_index = header_keys.get(_header_key("Event Name"))

    def row_title_identity(row):
        parsed_date = _parse_sheet_date(str(row[date_index]).strip() if date_index is not None and date_index < len(row) else "")
        date_value = parsed_date.isoformat() if parsed_date else _header_key(str(row[date_index]).strip() if date_index is not None and date_index < len(row) else "")
        title_value = _header_key(str(row[title_index]).strip() if title_index is not None and title_index < len(row) else "")
        return "title:" + "|".join((date_value, title_value))

    def row_identity(row):
        reference = str(row[reference_index]).strip() if reference_index is not None and reference_index < len(row) else ""
        if reference:
            return "reference:" + reference
        parsed_date = _parse_sheet_date(str(row[date_index]).strip() if date_index is not None and date_index < len(row) else "")
        date_value = parsed_date.isoformat() if parsed_date else _header_key(str(row[date_index]).strip() if date_index is not None and date_index < len(row) else "")
        promoter_value = _header_key(str(row[promoter_index]).strip() if promoter_index is not None and promoter_index < len(row) else "")
        venue_value = _header_key(str(row[venue_index]).strip() if venue_index is not None and venue_index < len(row) else "")
        event_type_value = _header_key(str(row[event_type_index]).strip() if event_type_index is not None and event_type_index < len(row) else "")
        return "composite:" + "|".join((date_value, promoter_value, venue_value, event_type_value))

    def merge_rows(current, incoming):
        width = max(len(current), len(incoming), len(headers))
        merged = list(current) + [""] * (width - len(current))
        incoming = list(incoming) + [""] * (width - len(incoming))
        for index, value in enumerate(incoming):
            if not str(merged[index]).strip() and str(value).strip():
                merged[index] = value
        return merged

    existing_custom = {}
    existing_by_title = {}
    for row in existing[1:]:
        if row and any(str(value).strip() for value in row):
            identity = row_identity(row)
            existing_custom[identity] = merge_rows(existing_custom[identity], row) if identity in existing_custom else list(row)
            title_identity = row_title_identity(row)
            existing_by_title[title_identity] = merge_rows(existing_by_title[title_identity], row) if title_identity in existing_by_title else list(row)
    bookings = Booking.objects.filter(organization=tracker.organization).select_related("artist", "venue", "promoter").order_by("event_date", "title", "reference")
    output = [headers]
    seen_booking_keys = set()
    for booking in bookings:
        values = _booking_values(booking)
        booking_key = (booking.event_date.isoformat(), (values.get("title") or "").strip().casefold(), (values.get("promoter_name") or "").strip().casefold(), (values.get("venue_name") or "").strip().casefold(), (values.get("event_type") or "").strip().casefold())
        if booking_key in seen_booking_keys:
            continue
        seen_booking_keys.add(booking_key)
        identity = "reference:" + booking.reference
        fallback_identity = "composite:" + "|".join((booking.event_date.isoformat(), (values.get("promoter_name") or "").strip().casefold(), (values.get("venue_name") or "").strip().casefold(), (values.get("event_type") or "").strip().casefold()))
        title_identity = "title:" + "|".join((booking.event_date.isoformat(), _header_key(booking.title)))
        row = list(existing_custom.get(identity) or existing_custom.get(fallback_identity) or existing_by_title.get(title_identity) or [])
        row.extend([""] * (len(headers) - len(row)))
        for field in fields:
            column_index = header_keys[_header_key(field["header"])]
            value = values.get(field["key"], "")
            if value or not str(row[column_index]).strip():
                row[column_index] = value
        for header, column_index in _custom_sheet_columns(headers):
            value = values.get("custom_fields", {}).get(header, "")
            if value or not str(row[column_index]).strip():
                row[column_index] = value
        output.append(row[:len(headers)])
    _write_sheet_values(tracker, output)
    _clear_trailing_sheet_values(tracker, len(output) + 1, len(existing))
    _apply_export_format(tracker, len(existing), len(output), len(headers))
    return len(output) - 1, 0, 0, f"Exported {len(output) - 1} unique bookings to Google Sheets. Existing sheet values and formatting were preserved where Evolve had no replacement value. Commercial values and internal notes were not synced."



def _sheet_values_for_worksheet(tracker, worksheet_name):
    token = _google_access_token(tracker)
    encoded_range = urllib.parse.quote(f"'{worksheet_name}'!A:AZ", safe="")
    request = urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{urllib.parse.quote(tracker.spreadsheet_id, safe='')}/values/{encoded_range}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode()).get("values", [])
    except urllib.error.HTTPError as error:
        if error.code == 400:
            return []
        raise ValidationError(_google_sheets_error(error, "read")) from error
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValidationError("Google Sheets read failed while loading the release workbook tabs.") from error


def _import_release_rows(tracker, actor, request=None):
    headers, values = _sheet_table(tracker)
    if not headers:
        raise ValidationError("The release worksheet does not contain a readable header row.")
    normalized = {_header_key(header): index for index, header in enumerate(headers)}
    def value(row, *aliases):
        for alias in aliases:
            index = normalized.get(_header_key(alias))
            if index is not None and index < len(row) and str(row[index]).strip():
                return str(row[index]).strip()
        return ""
    first = next((row for row in values if any(str(x).strip() for x in row)), [])
    artist_name = value(first, "artist", "primary artist", "artist name")
    artists = list(Artist.objects.filter(organization=tracker.organization, status=Artist.Status.ACTIVE))
    configured_artist_id = (tracker.field_mapping or {}).get("artist_id") if isinstance(tracker.field_mapping, dict) else None
    artist = next((item for item in artists if str(item.id) == str(configured_artist_id)), None) if configured_artist_id else None
    artist = artist or (next((item for item in artists if item.stage_name.casefold() == artist_name.casefold()), None) if artist_name else (artists[0] if len(artists) == 1 else None))
    if not artist:
        raise ValidationError("Add an Artist column or ensure exactly one active artist exists for this release tracker.")
    raw_date = value(first, "release date", "planned release date")
    release_date = date(2026, 9, 1)
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%d %b %Y"):
        try:
            release_date = datetime.strptime(raw_date, pattern).date()
            break
        except ValueError:
            continue
    additional = {}
    for tab in ("Royalty Split Sheets", "Credits & Contributors", "Mixing & Mastering"):
        tab_values = _sheet_values_for_worksheet(tracker, tab)
        if tab_values:
            additional[tab] = tab_values
    release, imported = import_release_tracker(actor=actor, organization=tracker.organization, artist=artist, headers=headers, values=values, title=value(first, "release title", "release", "album title", "project title") or "Ts & Cs Apply", release_date=release_date, additional_sheets=additional, request=request)
    return imported, 0, 0, f"Imported {imported} tracks into {release.title}; related workbook tabs and track-level splits were reconciled."

def _parse_datetime(value, timezone_name, event_date=None):
    """Parse Google Sheets/Excel date-time values without forcing ISO syntax."""
    text = str(value or "").strip()
    if not text:
        return None
    parsed = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d %b %Y %H:%M", "%d %B %Y %H:%M", "%d/%m/%Y %I:%M %p", "%d %b %Y %I:%M %p"):
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue
    if parsed is None and event_date:
        normalized = text.lower().replace(".", "").replace("h", ":")
        for pattern in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I %p"):
            try:
                parsed_time = datetime.strptime(normalized, pattern).time()
                parsed = datetime.combine(event_date, parsed_time)
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValidationError(f"Invalid datetime/time in worksheet: {value}. Use YYYY-MM-DD HH:MM, DD/MM/YYYY HH:MM, or HH:MM with Event Date.")
    if timezone.is_naive(parsed):
        try:
            parsed = timezone.make_aware(parsed, ZoneInfo(timezone_name or "Africa/Johannesburg"))
        except (KeyError, ValueError):
            parsed = timezone.make_aware(parsed)
    return parsed


SHEET_HEADER_ALIASES = {
    "reference": ("booking reference", "reference", "booking id"),
    "title": ("event name", "event", "show name", "title"),
    "artist": ("artist", "performing artist", "artist name"),
    "status": ("status", "booking status"),
    "priority": ("priority",),
    "performance_type": ("performance type", "performance"),
    "event_type": ("event type", "event category"),
    "event_date": ("event date", "date", "show date"),
    "event_start_datetime": ("performance start", "performance time", "start time"),
    "event_end_datetime": ("performance end", "end time"),
    "timezone": ("timezone", "time zone"),
    "venue_name": ("venue", "venue name"),
    "venue_address": ("venue address", "address"),
    "city": ("city", "town"),
    "country": ("country",),
    "promoter_name": ("promoter", "promoter name"),
    "promoter_email": ("promoter email", "promoter email address"),
    "promoter_phone": ("promoter phone", "promoter contact", "promoter contact number"),
    "venue_contact_email": ("venue email", "venue email address"),
    "venue_contact_phone": ("venue phone", "venue contact", "venue contact number"),
    "currency": ("currency", "currency code"),
    "performance_fee": ("performance fee", "fee", "artist fee"),
    "deposit_amount": ("deposit", "deposit amount", "deposit fee"),
    "deposit_due_date": ("deposit due", "deposit due date"),
    "balance_due_date": ("balance due", "balance due date"),
    "comment": ("comment", "comments", "notes", "remarks"),
}


def _sheet_table(tracker):
    values = _sheet_values(tracker)
    if not values:
        return [], []
    header_index = next(
        (index for index, row in enumerate(values) if sum(bool(str(value).strip()) for value in row) >= 2),
        None,
    )
    if header_index is None:
        return [], []
    headers = [str(value).strip() for value in values[header_index]]
    return headers, values[header_index + 1:]


def _sheet_field_indexes(tracker, headers):
    indexes = {_header_key(header): index for index, header in enumerate(headers)}
    configured = tracker.field_mapping if isinstance(tracker.field_mapping, dict) else {}
    overrides = configured.get("headers", {}) if isinstance(configured.get("headers", {}), dict) else {}
    keys = {}
    for field in _safe_fields(tracker):
        candidates = (overrides.get(field["key"]), field["header"], *SHEET_HEADER_ALIASES.get(field["key"], ()))
        keys[field["key"]] = next((indexes.get(_header_key(candidate)) for candidate in candidates if candidate and _header_key(candidate) in indexes), None)
    return keys


def _custom_sheet_columns(headers):
    known = set()
    for field in _safe_fields(type("TrackerShape", (), {"kind": Tracker.Kind.BOOKINGS, "field_mapping": {}})()):
        known.add(_header_key(field["header"]))
        known.update(_header_key(alias) for alias in SHEET_HEADER_ALIASES.get(field["key"], ()))
    return [
        (header, index)
        for index, header in enumerate(headers)
        if header.strip() and _header_key(header) not in known
    ]


def _is_placeholder(value):
    return _header_key(value) in {"", "tbc", "tbd", "to be confirmed", "n/a", "na", "none", "-"}


def _safe_email(value):
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    try:
        validate_email(candidate)
    except ValidationError:
        return ""
    return candidate


def _unique_slug(model, organization, name):
    base = slugify(name)[:110] or "imported-record"
    candidate = base
    suffix = 2
    while model.objects.filter(organization=organization, slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _split_travelling_party(value):
    names = []
    seen = set()
    for part in re.split(r"[,\n]+", str(value or "")):
        name = " ".join(part.split()).strip(" -")
        if not name or name.lower() in {"tbc", "n/a", "na", "-"}:
            continue
        key = name.casefold()
        if key not in seen:
            names.append(name)
            seen.add(key)
    return names


def _import_travelling_party_contacts(tracker, actor, value, request=None):
    if not user_has_organization_permission(actor, tracker.organization, "contact.manage"):
        return
    for name in _split_travelling_party(value):
        parts = name.split(" ", 1)
        first_name, last_name = parts[0], parts[1] if len(parts) > 1 else ""
        existing = Contact.objects.filter(
            organization=tracker.organization,
            first_name__iexact=first_name,
            last_name__iexact=last_name,
        ).first()
        if not existing:
            create_contact(
                actor=actor,
                organization=tracker.organization,
                data={"first_name": first_name, "last_name": last_name, "job_title": "Travelling party"},
                request=request,
            )


def _import_promoter(tracker, actor, row, request=None):
    name = row.get("promoter_name", "").strip()
    if _is_placeholder(name):
        return None
    promoter = Promoter.objects.filter(organization=tracker.organization, name__iexact=name).first()
    data = {
        "name": name,
        "email": _safe_email(row.get("promoter_email", "")),
        "phone": row.get("promoter_phone", "").strip(),
        "status": Promoter.Status.ACTIVE,
    }
    can_manage = user_has_organization_permission(actor, tracker.organization, "promoter.manage")
    if not promoter and can_manage:
        return create_promoter(
            actor=actor,
            organization=tracker.organization,
            data={**data, "slug": _unique_slug(Promoter, tracker.organization, name)},
            request=request,
        )
    if promoter and can_manage:
        changes = {field: value for field, value in data.items() if value and getattr(promoter, field) != value}
        if changes:
            promoter = update_promoter(actor=actor, promoter=promoter, data=changes, request=request)
    return promoter


def _import_venue(tracker, actor, row, request=None):
    name = row.get("venue_name", "").strip()
    if _is_placeholder(name):
        return None
    venue = Venue.objects.filter(organization=tracker.organization, name__iexact=name).first()
    data = {
        "name": name,
        "address_line_1": row.get("venue_address", "").strip(),
        "city": row.get("city", "").strip(),
        "public_email": _safe_email(row.get("venue_contact_email", "")),
        "public_phone": row.get("venue_contact_phone", "").strip(),
        "status": Venue.Status.ACTIVE,
    }
    can_manage = user_has_organization_permission(actor, tracker.organization, "venue.manage")
    if not venue and can_manage:
        return create_venue(
            actor=actor,
            organization=tracker.organization,
            data={**data, "slug": _unique_slug(Venue, tracker.organization, name)},
            request=request,
        )
    if venue and can_manage:
        changes = {field: value for field, value in data.items() if value and getattr(venue, field) != value}
        if changes:
            venue = update_venue(actor=actor, venue=venue, data=changes, request=request)
    return venue


def _decimal_value(value):
    text = str(value or "").strip().replace(",", "")
    if not text or _is_placeholder(text):
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        raise ValidationError(f"Invalid money value in worksheet: {value}")


def _priority_value(value):
    normalized = _header_key(value)
    if normalized in {"low", "normal", "high", "urgent"}:
        return normalized
    return Booking.Priority.NORMAL


def _status_value(value):
    normalized = _header_key(value)
    if not normalized:
        return ""
    if any(word in normalized for word in ("cancel", "declin")):
        return "cancelled" if "cancel" in normalized else "declined"
    if any(word in normalized for word in ("confirm", "confimed", "invoice", "deposit paid", "fully paid")):
        return "confirmed"
    if "complete" in normalized or "performed" in normalized:
        return "completed"
    if "hold" in normalized:
        return "hold"
    if "pending" in normalized:
        return "pending"
    if "enquiry" in normalized or "inquiry" in normalized:
        return "enquiry"
    return normalized if normalized in {choice for choice, _ in Booking.Status.choices} else ""


def _parse_sheet_date(value):
    text = str(value).strip()
    if not text:
        return None
    current_year = timezone.localdate().year
    try:
        serial = float(text)
        if serial.is_integer() and 1 <= serial <= 80000:
            return date(1899, 12, 30) + timedelta(days=int(serial))
    except ValueError:
        pass
    for pattern in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y", "%d %b", "%d %B"):
        try:
            parsed = date.fromisoformat(text) if pattern == "%Y-%m-%d" else datetime.strptime(text, pattern).date()
            return parsed.replace(year=current_year) if "%Y" not in pattern else parsed
        except ValueError:
            continue
    return None


def _import_booking_rows(tracker, actor, request=None):
    headers, values = _sheet_table(tracker)
    if not headers:
        return 0, 0, 0, "The worksheet does not contain a readable header row."
    keys = _sheet_field_indexes(tracker, headers)
    header_indexes = {_header_key(header): index for index, header in enumerate(headers)}
    comment_index = next((header_indexes.get(alias) for alias in ("comment", "comments", "notes", "remarks") if alias in header_indexes), None)
    travel_party_index = next((header_indexes.get(alias) for alias in ("traveling party", "travelling party", "travel party", "travellers", "travelers") if alias in header_indexes), None)
    custom_columns = _custom_sheet_columns(headers)
    active_artists = list(Artist.objects.filter(organization=tracker.organization, status=Artist.Status.ACTIVE))
    fallback_artist = active_artists[0] if len(active_artists) == 1 else None
    created = updated = skipped = 0
    for raw in values:
        row = {key: (str(raw[index]).strip() if index is not None and index < len(raw) else "") for key, index in keys.items()}
        if comment_index is not None and comment_index < len(raw):
            row["comment"] = str(raw[comment_index]).strip()
        if travel_party_index is not None and travel_party_index < len(raw):
            _import_travelling_party_contacts(tracker, actor, raw[travel_party_index], request)
        custom_fields = {
            header: str(raw[index]).strip()
            for header, index in custom_columns
            if index < len(raw) and str(raw[index]).strip()
        }
        if row.get("comment"):
            custom_fields.setdefault("Comment", row["comment"])
        if travel_party_index is not None and travel_party_index < len(raw):
            travel_party = str(raw[travel_party_index]).strip()
            if travel_party:
                custom_fields.setdefault("Travel Party", travel_party)
        if not any(row.values()) and not custom_fields:
            continue
        artist = Artist.objects.filter(organization=tracker.organization, stage_name__iexact=row.get("artist", ""), status=Artist.Status.ACTIVE).first() if row.get("artist") else fallback_artist
        event_date = _parse_sheet_date(row.get("event_date", ""))
        if not artist or not event_date:
            skipped += 1
            continue
        if not row.get("title"):
            row["title"] = f"{artist.stage_name} booking - {event_date.isoformat()}"
        promoter = _import_promoter(tracker, actor, row, request)
        venue = _import_venue(tracker, actor, row, request)
        if _header_key(row.get("priority", "")) in {"tbc", "tbd", "to be confirmed", "n/a", "na"}:
            custom_fields.setdefault("Source Priority", row.get("priority", ""))
        if _header_key(row.get("status", "")) in {"tbc", "tbd", "to be confirmed", "n/a", "na"}:
            custom_fields.setdefault("Source Status", row.get("status", ""))
        commercial = {
            "currency": ((row.get("currency") or "ZAR").upper() if not _is_placeholder(row.get("currency")) else "ZAR"),
            "performance_fee": _decimal_value(row.get("performance_fee")),
            "deposit_amount": _decimal_value(row.get("deposit_amount")),
            "deposit_due_date": _parse_sheet_date(row.get("deposit_due_date", "")),
            "balance_due_date": _parse_sheet_date(row.get("balance_due_date", "")),
        }
        if not user_has_organization_permission(actor, tracker.organization, "booking.commercial.manage"):
            for key, value in commercial.items():
                if value not in (None, "", "ZAR"):
                    custom_fields.setdefault(f"Source {key.replace('_', ' ').title()}", str(value))
            commercial = {}
        data = {"title": row["title"], "artist": artist, "promoter": promoter, "venue": venue, "event_date": event_date, "event_start_datetime": _parse_datetime(row.get("event_start_datetime", ""), row.get("timezone", ""), event_date), "event_end_datetime": _parse_datetime(row.get("event_end_datetime", ""), row.get("timezone", ""), event_date), "timezone": row.get("timezone") or "Africa/Johannesburg", "performance_type": row.get("performance_type", ""), "event_type": row.get("event_type", ""), "priority": _priority_value(row.get("priority", "")), "custom_fields": custom_fields, **commercial}
        booking = Booking.objects.filter(organization=tracker.organization, reference=row.get("reference", "")).first() if row.get("reference") else None
        if not booking:
            booking = Booking.objects.filter(
                organization=tracker.organization,
                artist=artist,
                event_date=event_date,
                title=data["title"],
            ).first()
        if not booking:
            candidates = Booking.objects.filter(
                organization=tracker.organization,
                artist=artist,
                event_date=event_date,
            ).order_by("-updated_at", "-created_at")
            promoter_name = _header_key(row.get("promoter_name", ""))
            venue_name = _header_key(row.get("venue_name", ""))
            if promoter_name:
                candidates = candidates.filter(promoter_name_snapshot__iexact=row.get("promoter_name", "").strip())
            if venue_name:
                candidates = candidates.filter(venue_name_snapshot__iexact=row.get("venue_name", "").strip())
            if promoter_name or venue_name:
                booking = candidates.first()
        if booking:
            status_text = row.get("status", "")
            requested_status = _status_value(status_text)
            merged_custom_fields = dict(booking.custom_fields or {})
            merged_custom_fields.update(custom_fields)
            data["custom_fields"] = merged_custom_fields
            update_data = {key: value for key, value in data.items() if value is not None}
            for key in (
                "promoter",
                "venue",
            ):
                if data.get(key) is None:
                    update_data.pop(key, None)
            for key in (
                "performance_type",
                "event_type",
                "timezone",
                "priority",
            ):
                if _is_placeholder(row.get(key, "")):
                    update_data.pop(key, None)
            if _is_placeholder(row.get("currency", "")):
                update_data.pop("currency", None)
            update_booking(actor=actor, booking=booking, data=update_data, request=request)
            if requested_status and requested_status != booking.status:
                try:
                    transition_booking(actor=actor, booking=booking, to_status=requested_status, reason="Imported from Google Sheets", request=request)
                except ValidationError:
                    skipped += 1
                    continue
            updated += 1
        else:
            status_text = row.get("status", "")
            normalized_status = _status_value(status_text)
            if normalized_status:
                data["status"] = normalized_status
            booking = create_booking(actor=actor, organization=tracker.organization, data=data, request=request)
            if not promoter or not venue:
                booking.promoter_name_snapshot = row.get("promoter_name", "")
                booking.venue_name_snapshot = row.get("venue_name", "")
                booking.city_snapshot = row.get("city", "")
                booking.save(update_fields=("promoter_name_snapshot", "venue_name_snapshot", "city_snapshot", "updated_at"))
            created += 1
    return created, updated, skipped, f"Imported {created} new and updated {updated} bookings; skipped {skipped} rows."

def _google_access_token(tracker):
    connector = tracker.google_connector
    refresh_reference = connector.refresh_token_reference
    if not refresh_reference:
        raise ValidationError("Add a Google OAuth refresh-token reference before live Sheets reconciliation.")
    client_id = resolve_secret(connector.secret_backend, connector.client_id_reference)
    client_secret = resolve_secret(connector.secret_backend, connector.client_secret_reference)
    refresh_token = resolve_secret(connector.secret_backend, refresh_reference)
    if not client_id or not client_secret or not refresh_token:
        raise ValidationError("Google OAuth references are not configured on the server.")
    payload = urllib.parse.urlencode({"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"}).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {}
        reason = detail.get("error_description") or detail.get("error") or "Google rejected the refresh token"
        raise ValidationError(f"Google OAuth token exchange failed: {reason}.") from error
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise ValidationError("Google OAuth token exchange failed: Google was unreachable or returned invalid JSON.") from error
    token = data.get("access_token")
    if not token:
        raise ValidationError("Google OAuth did not return an access token.")
    return token


def _sheet_headers(tracker):
    headers, _ = _sheet_table(tracker)
    return [header for header in headers if header.strip()]


def _update_sheet_headers(tracker, columns):
    token = _google_access_token(tracker)
    current = _sheet_values(tracker)
    old_headers = current[0] if current else []
    old_indexes = {_header_key(header): index for index, header in enumerate(old_headers)}
    remapped = [list(columns)]
    for row in current[1:]:
        remapped.append([
            row[old_indexes[_header_key(header)]] if _header_key(header) in old_indexes and old_indexes[_header_key(header)] < len(row) else ""
            for header in columns
        ])
    body = json.dumps({"valueInputOption": "RAW", "data": [{"range": f"'{tracker.worksheet_name}'!A1", "majorDimension": "ROWS", "values": remapped}]}).encode()
    request = urllib.request.Request(f"https://sheets.googleapis.com/v4/spreadsheets/{urllib.parse.quote(tracker.spreadsheet_id, safe='')}/values:batchUpdate", data=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20):
            return
    except urllib.error.HTTPError as error:
        raise ValidationError(_google_sheets_error(error, "header update")) from error
    except urllib.error.URLError as error:
        raise ValidationError("Google Sheets header update failed.") from error
