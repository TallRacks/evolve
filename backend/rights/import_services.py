import csv
import hashlib
import io
import zipfile
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from audit.services import record_event
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import RoyaltyStatement, RoyaltyStatementLine
from .services import require


ALIASES = {
    "release_title": ("release_title", "release", "album", "product"),
    "description": ("description", "track", "track_title", "title", "song"),
    "upc_ean": ("upc", "upc_ean", "ean", "barcode"),
    "isrc": ("isrc", "track_isrc"),
    "territory_code": ("territory", "territory_code", "country"),
    "platform": ("platform", "service", "store"),
    "usage_type": ("usage_type", "usage", "type"),
    "rights_basis": ("rights_basis", "basis", "right_basis"),
    "quantity": ("quantity", "units", "streams", "plays"),
    "gross_amount": ("gross", "gross_amount", "revenue", "amount", "earnings"),
    "deductions": ("deductions", "deduction", "fees", "withheld"),
    "sequence": ("sequence", "track_number", "track_no", "number"),
}


def _normalise_key(value):
    return "".join(
        character
        for character in str(value or "").strip().lower()
        if character.isalnum()
    )


def _columns(fieldnames):
    normalised = {_normalise_key(name): name for name in fieldnames if name}
    return {
        field: next(
            (
                normalised[_normalise_key(alias)]
                for alias in aliases
                if _normalise_key(alias) in normalised
            ),
            None,
        )
        for field, aliases in ALIASES.items()
    }


def _text(row, column):
    return str(row.get(column, "") or "").strip() if column else ""


def _decimal(row, column, *, default=None):
    value = _text(row, column).replace(",", "")
    if not value:
        return default
    try:
        return Decimal(value.replace(" ", ""))
    except InvalidOperation as exc:
        raise ValidationError(f"Invalid number: {value}.") from exc


def _xlsx_rows(uploaded):
    """Read the first worksheet from a small XLSX workbook without a new runtime dependency."""
    try:
        archive = zipfile.ZipFile(uploaded)
    except zipfile.BadZipFile as exc:
        raise ValidationError("The XLSX file could not be opened.") from exc
    with archive:
        names = set(archive.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.itertext()) for node in root]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationships = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in rels
            if item.attrib.get("Type", "").endswith("/worksheet")
        }
        sheet = next(iter(workbook.findall(".//{*}sheet")), None)
        if sheet is None:
            raise ValidationError("The XLSX workbook does not contain a worksheet.")
        target = relationships.get(
            sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
        )
        if not target:
            raise ValidationError("The XLSX worksheet relationship is invalid.")
        worksheet_path = target.lstrip("/")
        if not worksheet_path.startswith("xl/"):
            worksheet_path = f"xl/{worksheet_path}"
        root = ElementTree.fromstring(archive.read(worksheet_path))
        rows = []
        for row in root.findall(".//{*}row"):
            values = {}
            for cell in row.findall("{*}c"):
                reference = cell.attrib.get("r", "")
                column = "".join(character for character in reference if character.isalpha())
                value = cell.find("{*}v")
                inline = cell.find("{*}is")
                text = "" if value is None else value.text or ""
                if cell.attrib.get("t") == "s" and text:
                    text = shared[int(text)] if int(text) < len(shared) else ""
                elif cell.attrib.get("t") == "inlineStr" and inline is not None:
                    text = "".join(inline.itertext())
                values[column] = text
            rows.append(values)
        if not rows:
            raise ValidationError("The XLSX worksheet is empty.")
        letters = sorted(
            {key for row in rows for key in row},
            key=lambda value: (len(value), value),
        )
        headers = [rows[0].get(letter, "") for letter in letters]
        return headers, [
            {
                headers[index]: row.get(letters[index], "")
                for index in range(len(letters))
                if headers[index]
            }
            for row in rows[1:]
        ]


def _uploaded_rows(uploaded):
    filename = str(getattr(uploaded, "name", "")).lower()
    if filename.endswith(".csv"):
        raw = uploaded.read(8_000_001)
        if len(raw) > 8_000_000:
            raise ValidationError("Royalty files must be 8 MB or smaller.")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("Royalty CSV must be UTF-8 encoded.") from exc
        reader = csv.DictReader(io.StringIO(text))
        return reader.fieldnames, list(reader)
    if filename.endswith(".xlsx"):
        raw = uploaded.read(8_000_001)
        if len(raw) > 8_000_000:
            raise ValidationError("Royalty files must be 8 MB or smaller.")
        return _xlsx_rows(io.BytesIO(raw))
    raise ValidationError("Upload a CSV or XLSX royalty statement.")


@transaction.atomic
def import_statement_csv(*, actor, statement, uploaded, request=None):
    require(actor, statement.organization, "royalties.manage")
    locked = RoyaltyStatement.objects.select_for_update().get(pk=statement.pk)
    if locked.status != RoyaltyStatement.Status.DRAFT:
        raise ValidationError("Only draft statements can receive imported lines.")
    fieldnames, rows = _uploaded_rows(uploaded)
    if not fieldnames:
        raise ValidationError("The CSV must include a header row.")
    columns = _columns(fieldnames)
    if not columns["gross_amount"]:
        raise ValidationError("The CSV needs a gross, revenue, amount, or earnings column.")
    existing = set(locked.lines.values_list("external_track_reference", flat=True))
    imported = skipped = 0
    errors = []
    for index, row in enumerate(rows, start=2):
        title = _text(row, columns["description"])
        release_title = _text(row, columns["release_title"])
        isrc = _text(row, columns["isrc"])
        gross = _decimal(row, columns["gross_amount"])
        if gross is None:
            errors.append(f"Row {index}: missing gross amount.")
            continue
        deductions = _decimal(row, columns["deductions"], default=Decimal("0")) or Decimal("0")
        sequence = _text(row, columns["sequence"])
        try:
            sequence_number = int(sequence) if sequence else index - 1
        except ValueError:
            sequence_number = index - 1
        fingerprint = hashlib.sha256(
            "|".join(
                (release_title, title, isrc, str(gross), str(deductions), str(sequence_number))
            ).encode()
        ).hexdigest()[:40]
        reference = f"csv:{fingerprint}"
        if reference in existing:
            skipped += 1
            continue
        RoyaltyStatementLine.objects.create(
            statement=locked,
            external_track_reference=reference,
            release_title=release_title,
            upc_ean=_text(row, columns["upc_ean"]),
            isrc=isrc,
            territory_code=_text(row, columns["territory_code"]).upper() or "WORLDWIDE",
            platform=_text(row, columns["platform"]),
            usage_type=_text(row, columns["usage_type"]),
            rights_basis=(
                _text(row, columns["rights_basis"]).lower()
                or RoyaltyStatementLine.Basis.OTHER
            ),
            quantity=_decimal(row, columns["quantity"]),
            gross_amount=gross,
            deductions=deductions,
            description=title or release_title or f"Imported row {index}",
            sequence=sequence_number,
        )
        existing.add(reference)
        imported += 1
    if errors and not imported and not skipped:
        raise ValidationError({"file": errors[:20]})
    record_event(
        actor=actor,
        organization=locked.organization,
        action="royalties.statement_lines_imported",
        resource=locked,
        description=(
            f"Imported {imported} royalty statement lines; "
            f"skipped {skipped} existing lines."
        ),
        request=request,
    )
    return {"imported": imported, "skipped": skipped, "errors": errors[:20]}
