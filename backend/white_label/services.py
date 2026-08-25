import hashlib
import secrets
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from organizations.permissions import user_has_organization_permission

from .models import APIClient, APIKey, OrganizationBranding, OrganizationDomain

DEFAULT_BRANDING = {
    "brand_name": "Evolve",
    "logo_url": "",
    "favicon_url": "",
    "primary": "#D6A84B",
    "secondary": "#A3A3A3",
    "accent": "#F0C96B",
    "background": "#0A0A0A",
    "surface": "#171717",
    "text_primary": "#FAFAFA",
    "text_muted": "#A3A3A3",
    "support_email": "",
    "support_url": "",
}
ALLOWED_SCOPES = (
    "profile.read",
    "organization.read",
    "team.read",
    "artist.read",
    "promoter.read",
    "venue.read",
    "booking.read",
    "callsheet.read",
    "music.read",
    "campaign.read",
    "calendar.read",
    "document.read",
    "finance.read",
    "rights.read",
    "travel.read",
    "production.read",
)


def effective_branding(organization):
    try:
        branding = organization.branding
    except OrganizationBranding.DoesNotExist:
        return {**DEFAULT_BRANDING, "brand_name": organization.name}
    return {
        "brand_name": branding.display_name or organization.name,
        "logo_url": branding.logo_url,
        "favicon_url": branding.favicon_url,
        "primary": branding.primary_color,
        "secondary": branding.secondary_color,
        "accent": branding.accent_color,
        "background": branding.background_color,
        "surface": branding.surface_color,
        "text_primary": branding.text_color,
        "text_muted": branding.text_muted_color,
        "support_email": branding.support_email,
        "support_url": branding.support_url,
    }


def require_manage(user, organization, permission):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionDenied("You do not have permission for this organization.")


def create_domain(*, organization, hostname):
    token = secrets.token_urlsafe(32)
    domain = OrganizationDomain(
        organization=organization, hostname=hostname, verification_token=token
    )
    domain.full_clean()
    domain.save()
    return domain


def verify_domain(domain):
    domain.verification_status = OrganizationDomain.VerificationStatus.VERIFIED
    domain.verified_at = timezone.now()
    domain.save(update_fields=("verification_status", "verified_at", "updated_at"))
    return domain


@dataclass(frozen=True)
class CreatedKey:
    key: APIKey
    secret: str


def _digest(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


@transaction.atomic
def create_api_client_key(*, organization, name, description, scopes, created_by, expires_at=None):
    invalid = set(scopes) - set(ALLOWED_SCOPES)
    if invalid:
        raise ValidationError("One or more API scopes are invalid.")
    client = APIClient.objects.create(
        organization=organization, name=name, description=description, created_by=created_by
    )
    prefix = secrets.token_hex(6)
    raw = secrets.token_urlsafe(32)
    secret = f"evolve_{prefix}_{raw}"
    key = APIKey.objects.create(
        client=client,
        key_prefix=prefix,
        secret_digest=_digest(secret),
        scopes=sorted(set(scopes)),
        expires_at=expires_at,
    )
    return client, CreatedKey(key=key, secret=secret)


def authenticate_api_key(raw_secret, required_scope=None):
    try:
        prefix = raw_secret.split("_", 2)[1]
        key = APIKey.objects.select_related("client", "client__organization").get(
            key_prefix=prefix, secret_digest=_digest(raw_secret)
        )
    except (IndexError, APIKey.DoesNotExist):
        raise PermissionDenied("Invalid API credentials.") from None
    now = timezone.now()
    if key.revoked_at or not key.client.is_active or not key.client.organization.is_active:
        raise PermissionDenied("Invalid API credentials.")
    if key.expires_at and key.expires_at <= now:
        raise PermissionDenied("Invalid API credentials.")
    if required_scope and required_scope not in key.scopes:
        raise PermissionDenied("Insufficient API scope.")
    APIKey.objects.filter(pk=key.pk).update(last_used_at=now)
    key.last_used_at = now
    return key


def organization_for_host(host):
    hostname = host.split(":", 1)[0].lower().rstrip(".")
    domain = (
        OrganizationDomain.objects.select_related("organization")
        .filter(
            hostname=hostname,
            verification_status=OrganizationDomain.VerificationStatus.VERIFIED,
            is_active=True,
            is_primary=True,
            organization__is_active=True,
        )
        .first()
    )
    return domain.organization if domain else None
