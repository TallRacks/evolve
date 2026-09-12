import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .mobile_models import MobileCredential, MobileDevice

ACCESS_LIFETIME = timedelta(minutes=15)
REFRESH_LIFETIME = timedelta(days=14)


def digest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _credential(device, kind, lifetime):
    raw = secrets.token_urlsafe(48)
    MobileCredential.objects.create(
        device=device,
        kind=kind,
        token_digest=digest_token(raw),
        expires_at=timezone.now() + lifetime,
    )
    return raw


@transaction.atomic
def issue_tokens(device):
    device.last_seen_at = timezone.now()
    device.save(update_fields=("last_seen_at", "updated_at"))
    return {
        "access": _credential(device, MobileCredential.Kind.ACCESS, ACCESS_LIFETIME),
        "refresh": _credential(device, MobileCredential.Kind.REFRESH, REFRESH_LIFETIME),
        "access_expires_in": int(ACCESS_LIFETIME.total_seconds()),
        "refresh_expires_in": int(REFRESH_LIFETIME.total_seconds()),
    }


@transaction.atomic
def revoke_device(device):
    now = timezone.now()
    device.status = MobileDevice.Status.REVOKED
    device.revoked_at = now
    device.save(update_fields=("status", "revoked_at", "updated_at"))
    MobileCredential.objects.filter(device=device, revoked_at__isnull=True).update(revoked_at=now)


@transaction.atomic
def revoke_all_devices(user):
    for device in MobileDevice.objects.select_for_update().filter(
        user=user, status=MobileDevice.Status.ACTIVE
    ):
        revoke_device(device)


@transaction.atomic
def rotate_refresh(raw_token):
    credential = (
        MobileCredential.objects.select_for_update()
        .select_related("device", "device__user")
        .filter(kind=MobileCredential.Kind.REFRESH, token_digest=digest_token(raw_token))
        .first()
    )
    if credential is None:
        return None, "invalid"
    if credential.rotated_at is not None:
        revoke_device(credential.device)
        return None, "reused"
    if not credential.usable:
        return None, "expired"
    credential.rotated_at = timezone.now()
    credential.save(update_fields=("rotated_at", "updated_at"))
    return issue_tokens(credential.device), None
