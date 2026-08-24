from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification, NotificationPreference
from notifications.selectors import inbox, unread_count
from notifications.services import archive, mark_all_read, mark_read, update_preferences
from organizations.api.permissions import PlatformSuperuser

from .serializers import PreferenceSerializer, ReadSerializer, RecipientSerializer


class ListView(APIView):
    def get(self, request):
        qs = inbox(request.user)
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
        current = {
            item.category: item.in_app_enabled
            for item in NotificationPreference.objects.filter(user=request.user)
        }
        return Response(
            [
                {"category": category, "in_app_enabled": current.get(category, True)}
                for category in Notification.Category.values
            ]
        )

    def patch(self, request):
        serializer = PreferenceSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        update_preferences(
            request.user,
            {item["category"]: item["in_app_enabled"] for item in serializer.validated_data},
            request=request,
        )
        return self.get(request)


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
