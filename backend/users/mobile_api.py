from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .api.serializers import LoginSerializer, SessionBootstrapSerializer
from .authentication import MobileOpaqueAuthentication
from .mobile_models import MobileDevice
from .mobile_services import (
    digest_token,
    issue_tokens,
    revoke_all_devices,
    revoke_device,
    rotate_refresh,
)


class MobileLoginSerializer(LoginSerializer):
    device_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    platform = serializers.CharField(required=False, allow_blank=True, max_length=24)
    app_version = serializers.CharField(required=False, allow_blank=True, max_length=32)


def mobile_response(user, device, tokens):
    return {
        "tokens": tokens,
        "device": {"id": device.pk, "name": device.name, "platform": device.platform},
        "session": SessionBootstrapSerializer(user).data,
    }


@method_decorator(csrf_exempt, name="dispatch")
class MobileLoginView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        serializer = MobileLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request=request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST
            )
        device = MobileDevice.objects.create(
            user=user,
            name=serializer.validated_data.get("device_name", ""),
            platform=serializer.validated_data.get("platform", ""),
            app_version=serializer.validated_data.get("app_version", ""),
            last_seen_at=timezone.now(),
        )
        return Response(mobile_response(user, device, issue_tokens(device)))


@method_decorator(csrf_exempt, name="dispatch")
class MobileRefreshView(APIView):
    authentication_classes = ()
    permission_classes = ()

    def post(self, request):
        raw_token = request.data.get("refresh")
        if not isinstance(raw_token, str) or not raw_token:
            return Response(
                {"detail": "Refresh credential is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        tokens, error = rotate_refresh(raw_token)
        if error:
            code = "mobile_session_reused" if error == "reused" else "mobile_session_expired"
            return Response(
                {"detail": "Mobile session is no longer valid.", "code": code},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        device = MobileDevice.objects.select_related("user").get(
            credentials__token_digest=digest_token(tokens["refresh"])
        )
        return Response(mobile_response(device.user, device, tokens))


@method_decorator(csrf_exempt, name="dispatch")
class MobileSessionView(APIView):
    authentication_classes = (MobileOpaqueAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        remaining = max(
            0, int((request.mobile_credential.expires_at - timezone.now()).total_seconds())
        )
        return Response(
            mobile_response(
                request.user, request.mobile_credential.device, {"access_expires_in": remaining}
            )
        )


class MobileLogoutView(MobileSessionView):
    def post(self, request):
        revoke_device(request.mobile_credential.device)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MobileLogoutAllView(MobileSessionView):
    def post(self, request):
        revoke_all_devices(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MobileDevicesView(MobileSessionView):
    def get(self, request):
        return Response(
            [
                {
                    "id": d.pk,
                    "name": d.name,
                    "platform": d.platform,
                    "status": d.status,
                    "created_at": d.created_at,
                    "last_seen_at": d.last_seen_at,
                    "revoked_at": d.revoked_at,
                }
                for d in MobileDevice.objects.filter(user=request.user)
            ]
        )


class MobileDeviceRevokeView(MobileSessionView):
    def post(self, request, device_id):
        device = MobileDevice.objects.filter(id=device_id, user=request.user).first()
        if device is None:
            return Response({"detail": "Device not found."}, status=status.HTTP_404_NOT_FOUND)
        revoke_device(device)
        return Response(status=status.HTTP_204_NO_CONTENT)
