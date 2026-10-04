from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_event
from notifications.email_delivery import retry_delivery
from notifications.email_policy import CATEGORY_POLICIES
from notifications.models import DevicePushSubscription, EmailDeliveryAttempt, Notification
from notifications.selectors import inbox, unread_count
from notifications.services import (
    archive,
    mark_all_read,
    mark_read,
    preference_rows,
    reset_preferences,
    update_preferences,
)
from organizations.api.permissions import PlatformSuperuser

from .serializers import (
    DeliveryAttemptSerializer,
    PreferenceSerializer,
    ReadSerializer,
    RecipientSerializer,
)


class ListView(APIView):
    def get(self, request):
        qs = inbox(request.user).prefetch_related("notification__email_attempts")
        if request.query_params.get("unread") == "true":
            qs = qs.filter(read_at__isnull=True)
        for parameter, field in (
            ("priority", "notification__priority"),
            ("category", "notification__category"),
            ("type", "notification__notification_type"),
            ("organization", "notification__organization_id"),
        ):
            if request.query_params.get(parameter):
                qs = qs.filter(**{field: request.query_params[parameter]})
        page = Paginator(qs, 25).get_page(request.query_params.get("page", 1))
        return Response(
            {
                "count": page.paginator.count,
                "results": RecipientSerializer(page.object_list, many=True).data,
            }
        )


class UnreadCountView(APIView):
    def get(self, request):
        return Response({"count": unread_count(request.user)})


class PushSubscriptionView(APIView):
    def get(self, request):
        import os

        return Response({
            "enabled": bool(os.environ.get("EVOLVE_WEB_PUSH_PUBLIC_KEY")),
            "public_key": os.environ.get("EVOLVE_WEB_PUSH_PUBLIC_KEY", ""),
        })

    def post(self, request):
        endpoint = request.data.get("endpoint")
        keys = request.data.get("keys") or {}
        if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
            raise ValidationError("A valid Web Push subscription is required.")
        subscription, _ = DevicePushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": keys["p256dh"],
                "auth": keys["auth"],
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
                "is_active": True,
            },
        )
        return Response({"id": subscription.id, "active": True})

    def delete(self, request):
        endpoint = request.data.get("endpoint")
        DevicePushSubscription.objects.filter(endpoint=endpoint, user=request.user).update(is_active=False)
        return Response(status=204)


class ReadView(APIView):
    def post(self, request, notification_id):
        recipient = get_object_or_404(inbox(request.user), notification_id=notification_id)
        serializer = ReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            RecipientSerializer(mark_read(recipient, serializer.validated_data["read"])).data
        )


class ArchiveView(APIView):
    def post(self, request, notification_id):
        archive(get_object_or_404(inbox(request.user), notification_id=notification_id))
        return Response(status=204)


class MarkAllReadView(APIView):
    def post(self, request):
        mark_all_read(request.user)
        return Response(status=204)


class PreferenceView(APIView):
    def get(self, request):
        return Response(preference_rows(request.user))

    def patch(self, request):
        serializer = PreferenceSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        values = {
            item["category"]: {
                key: item[key] for key in ("in_app_enabled", "email_enabled") if key in item
            }
            for item in serializer.validated_data
        }
        unknown = set(values) - set(CATEGORY_POLICIES)
        if unknown:
            raise ValidationError({"category": "Unknown notification category."})
        update_preferences(request.user, values, request=request)
        return self.get(request)


class PreferenceResetView(APIView):
    def post(self, request):
        return Response(reset_preferences(request.user, request=request))


class PlatformView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request):
        qs = Notification.objects.select_related("organization").prefetch_related("recipients")
        for parameter, field in (
            ("organization", "organization_id"),
            ("category", "category"),
            ("priority", "priority"),
            ("type", "notification_type"),
        ):
            if request.query_params.get(parameter):
                qs = qs.filter(**{field: request.query_params[parameter]})
        return Response(
            [
                {
                    "id": item.id,
                    "notification_type": item.notification_type,
                    "category": item.category,
                    "priority": item.priority,
                    "organization": item.organization.name if item.organization else None,
                    "source_type": item.source_type,
                    "recipient_count": item.recipients.count(),
                    "created_at": item.created_at,
                }
                for item in qs[:200]
            ]
        )


class DeliveryListView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request):
        qs = EmailDeliveryAttempt.objects.select_related(
            "organization", "connector", "user", "notification"
        )
        for parameter, field in (
            ("status", "status"),
            ("category", "category"),
            ("organization", "organization_id"),
            ("connector", "connector_id"),
        ):
            if request.query_params.get(parameter):
                qs = qs.filter(**{field: request.query_params[parameter]})
        if request.query_params.get("date_from"):
            qs = qs.filter(attempted_at__date__gte=request.query_params["date_from"])
        if request.query_params.get("date_to"):
            qs = qs.filter(attempted_at__date__lte=request.query_params["date_to"])
        page = Paginator(qs, 50).get_page(request.query_params.get("page", 1))
        return Response(
            {
                "count": page.paginator.count,
                "results": DeliveryAttemptSerializer(page.object_list, many=True).data,
            }
        )


class DeliveryRetryView(APIView):
    permission_classes = [PlatformSuperuser]

    def post(self, request, attempt_id):
        attempt = get_object_or_404(EmailDeliveryAttempt, pk=attempt_id)
        try:
            retried = retry_delivery(attempt)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        if not retried:
            raise ValidationError("Email retry could not be scheduled safely.")
        record_event(
            actor=request.user,
            organization=attempt.organization,
            action="email.delivery_retried",
            resource=retried,
            description="Retried a transactional email delivery attempt.",
            request=request,
        )
        return Response(DeliveryAttemptSerializer(retried).data, status=201)
