import re

from django.core.exceptions import ValidationError

TOKEN = re.compile(r"{{\s*([a-z][a-z0-9_.]*)\s*}}")
ALLOWED_VARIABLES = {
    "organization.name",
    "artist.name",
    "booking.reference",
    "booking.event_name",
    "booking.date",
    "booking.start",
    "booking.end",
    "venue.name",
    "venue.address",
    "promoter.name",
}


def validate_template_text(value):
    tokens = set(TOKEN.findall(value))
    scrubbed = TOKEN.sub("", value)
    if any(marker in scrubbed for marker in ("{{", "}}", "{%", "%}", "{#", "#}")):
        raise ValidationError("Use only simple allowlisted template variables.")
    invalid = tokens - ALLOWED_VARIABLES
    if invalid:
        raise ValidationError(f"Unsupported template variables: {', '.join(sorted(invalid))}.")
    return tokens
