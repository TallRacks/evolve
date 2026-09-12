from datetime import UTC, datetime

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication as DRFSessionAuthentication
from rest_framework.exceptions import AuthenticationFailed

PASSWORD_AUTHENTICATED_AT = "password_authenticated_at"


def mark_password_fresh(request):
    request.session[PASSWORD_AUTHENTICATED_AT] = timezone.now().isoformat()


def password_is_fresh(request):
    value = request.session.get(PASSWORD_AUTHENTICATED_AT)
    if not value:
        return False
    try:
        authenticated_at = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    if authenticated_at.tzinfo is None:
        authenticated_at = authenticated_at.replace(tzinfo=UTC)
    age = (timezone.now() - authenticated_at).total_seconds()
    return 0 <= age < settings.MAX_PASSWORD_AUTH_AGE_SECONDS


class RawSessionAuthentication(DRFSessionAuthentication):
    def authenticate_header(self, request):
        return "Session"


class SessionAuthentication(RawSessionAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        allow_test_session = getattr(
            settings, "ALLOW_TEST_FORCE_LOGIN_WITHOUT_PASSWORD_FRESHNESS", False
        )
        if result and not password_is_fresh(request) and not allow_test_session:
            raise AuthenticationFailed(
                {
                    "detail": "Password reauthentication is required.",
                    "code": "reauthentication_required",
                }
            )
        return result

    def authenticate_header(self, request):
        return "Session"


class MobileOpaqueAuthentication:
    """Authenticates only short-lived opaque access credentials."""

    def authenticate(self, request):
        from .mobile_models import MobileCredential
        from .mobile_services import digest_token

        header = request.headers.get("Authorization", "")
        scheme, separator, raw_token = header.partition(" ")
        if not separator or scheme.lower() != "bearer" or not raw_token or " " in raw_token:
            return None
        credential = (
            MobileCredential.objects.select_related("device", "device__user")
            .filter(kind=MobileCredential.Kind.ACCESS, token_digest=digest_token(raw_token))
            .first()
        )
        if credential is None or not credential.usable:
            raise AuthenticationFailed("Mobile session is invalid or expired.")
        credential.device.last_seen_at = timezone.now()
        credential.device.save(update_fields=("last_seen_at", "updated_at"))
        request.mobile_credential = credential
        return credential.device.user, credential

    def authenticate_header(self, request):
        return "Bearer"
