import ipaddress
import re
import socket
from urllib.parse import urlparse

from django.core.exceptions import ValidationError

SECRET_REFERENCE = re.compile(r"^EVOLVE_[A-Z0-9_]{3,100}$")
EMAIL_SECRET_REFERENCE = re.compile(r"^EVOLVE_EMAIL_[A-Z0-9_]{3,94}$")
STORAGE_SECRET_REFERENCE = re.compile(r"^EVOLVE_STORAGE_[A-Z0-9_]{3,92}$")


def validate_secret_reference(value):
    if value and not SECRET_REFERENCE.fullmatch(value):
        raise ValidationError("Use an EVOLVE_ environment secret reference.")


def validate_email_secret_reference(value):
    if value and not EMAIL_SECRET_REFERENCE.fullmatch(value):
        raise ValidationError("Use an EVOLVE_EMAIL_ secret reference.")


def validate_storage_secret_reference(value):
    if value and not STORAGE_SECRET_REFERENCE.fullmatch(value):
        raise ValidationError("Use an EVOLVE_STORAGE_ secret reference.")


def validate_path_prefix(value):
    if not value:
        return
    if value.startswith(("/", "\\")) or ".." in value.split("/"):
        raise ValidationError("Use a relative storage prefix without traversal segments.")


def validate_storage_endpoint(value, *, resolve=False):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValidationError("Storage endpoint must be an HTTPS URL without embedded credentials.")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValidationError("Local storage endpoints are not permitted.")
    addresses = []
    try:
        addresses.append(ipaddress.ip_address(host))
    except ValueError:
        if resolve:
            try:
                addresses.extend(
                    ipaddress.ip_address(item[4][0])
                    for item in socket.getaddrinfo(
                        host, parsed.port or 443, type=socket.SOCK_STREAM
                    )
                )
            except OSError as error:
                raise ValidationError("Storage endpoint could not be resolved.") from error
    if any(not address.is_global for address in addresses):
        raise ValidationError("Storage endpoint must resolve only to public network addresses.")
