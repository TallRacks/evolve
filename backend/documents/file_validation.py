import hashlib
import re
import unicodedata
import zipfile
from pathlib import PurePath

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
}
INLINE_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/webp",
    "audio/mpeg", "audio/wav", "audio/mp4", "audio/flac",
}
CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
UNSAFE_TRAVEL_NAMES = re.compile(r"(?:passport|national[-_ ]?id|identity[-_ ]?card|visa)", re.I)


def sanitize_filename(value):
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.replace("\\", "/").split("/")[-1]
    value = CONTROL.sub("", value).strip().strip(".")
    value = re.sub(r"[^\w .()\[\]-]", "_", value, flags=re.UNICODE)
    if not value:
        value = "document"
    stem = PurePath(value).stem[:150].strip() or "document"
    suffix = PurePath(value).suffix.lower()[:12]
    return f"{stem}{suffix}"[:180]


def _ooxml_type(file):
    try:
        with zipfile.ZipFile(file) as archive:
            names = set(archive.namelist())
            if "word/document.xml" in names:
                return ALLOWED_TYPES[".docx"]
            if "xl/workbook.xml" in names:
                return ALLOWED_TYPES[".xlsx"]
            if "ppt/presentation.xml" in names:
                return ALLOWED_TYPES[".pptx"]
    except (zipfile.BadZipFile, OSError, ValueError):
        return None
    finally:
        file.seek(0)
    return None


def _detect(file, filename):
    suffix = PurePath(filename).suffix.lower()
    head = file.read(8192)
    file.seek(0)
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"fLaC"):
        return "audio/flac"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "audio/mpeg"
    if len(head) >= 12 and head[4:8] == b"ftyp" and head[8:12] in {b"M4A ", b"M4B ", b"isom", b"mp42"}:
        return "audio/mp4"
    if head.startswith(b"PK\x03\x04"):
        return _ooxml_type(file)
    if suffix in {".txt", ".csv"}:
        if b"\x00" in head:
            return None
        try:
            text = head.decode("utf-8-sig").lstrip().lower()
        except UnicodeDecodeError:
            return None
        if text.startswith(("<!doctype html", "<html", "<script", "#!")):
            return None
        return ALLOWED_TYPES[suffix]
    return None


def validate_upload(file, *, document_type=None):
    filename = sanitize_filename(file.name)
    suffix = PurePath(filename).suffix.lower()
    expected = ALLOWED_TYPES.get(suffix)
    if not expected:
        raise ValidationError({"file": "This file extension is not supported."})
    size = getattr(file, "size", None)
    limit = settings.EVOLVE_MAX_UPLOAD_BYTES
    from integrations.models import StoragePolicy

    policy = StoragePolicy.objects.first()
    if policy:
        configured = (
            policy.max_image_size_bytes
            if expected.startswith("image/")
            else policy.max_audio_size_bytes
            if expected.startswith("audio/")
            else policy.max_document_size_bytes
        )
        limit = min(limit, configured)
        if expected.startswith("audio/") and not policy.audio_upload_enabled:
            raise ValidationError({"file": "Audio uploads are disabled by the platform policy."})
    if size is None or size > limit:
        raise ValidationError({"file": f"File exceeds the {limit // (1024 * 1024)} MB limit."})
    detected = _detect(file, filename)
    if detected != expected:
        raise ValidationError({"file": "File content does not match an allowed document type."})
    if document_type == "travel" and UNSAFE_TRAVEL_NAMES.search(filename):
        raise ValidationError(
            {"file": "Passport, identity-card, and visa identity documents are not supported."}
        )
    digest = hashlib.sha256()
    for chunk in file.chunks():
        digest.update(chunk)
    file.seek(0)
    return {
        "original_filename": filename,
        "content_type": detected,
        "detected_content_type": detected,
        "file_size": size,
        "checksum_sha256": digest.hexdigest(),
    }
