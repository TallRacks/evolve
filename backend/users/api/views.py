from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.authentication import RawSessionAuthentication, mark_password_fresh
from users.models import SecurityEvent, User

from .serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordSerializer,
    SessionBootstrapSerializer,
)


def bootstrap_response(user):
    return SessionBootstrapSerializer(user).data


def security_context(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return {
        "ip_address": forwarded.split(",", 1)[0].strip() or request.META.get("REMOTE_ADDR"),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
    }


def record_security(request, event_type, success, user=None):
    return SecurityEvent.objects.create(
        user=user, event_type=event_type, success=success, **security_context(request)
    )


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            candidate = User.objects.filter(
                email__iexact=serializer.validated_data["email"], is_active=True
            ).first()
            record_security(request, SecurityEvent.Type.LOGIN_FAILURE, False, candidate)
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        mark_password_fresh(request)
        record_security(request, SecurityEvent.Type.LOGIN_SUCCESS, True, user)
        return Response(bootstrap_response(user))


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(bootstrap_response(request.user))


class LogoutView(APIView):
    authentication_classes = (RawSessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        record_security(request, SecurityEvent.Type.LOGOUT, True, request.user)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class ReauthenticateView(APIView):
    authentication_classes = (RawSessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = PasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["password"]):
            record_security(request, SecurityEvent.Type.REAUTH_FAILURE, False, request.user)
            return Response({"detail": "Invalid password."}, status=status.HTTP_400_BAD_REQUEST)
        mark_password_fresh(request)
        record_security(request, SecurityEvent.Type.REAUTH_SUCCESS, True, request.user)
        return Response(bootstrap_response(request.user))


class SecurityActivityView(APIView):
    def get(self, request):
        return Response(
            [
                {
                    "id": event.pk,
                    "event_type": event.event_type,
                    "success": event.success,
                    "ip_address": event.ip_address,
                    "client": event.user_agent,
                    "occurred_at": event.occurred_at,
                }
                for event in SecurityEvent.objects.filter(user=request.user)[:50]
            ]
        )


@method_decorator(csrf_protect, name="dispatch")
class PasswordChangeView(APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(serializer.validated_data["new_password"], request.user)
        except DjangoValidationError as error:
            raise ValidationError({"new_password": error.messages}) from error
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=("password", "updated_at"))
        update_session_auth_hash(request, request.user)
        mark_password_fresh(request)
        record_security(request, SecurityEvent.Type.PASSWORD_CHANGED, True, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
