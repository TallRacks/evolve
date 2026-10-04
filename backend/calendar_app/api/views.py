from datetime import datetime, time, timedelta

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from artists.models import Artist
from calendar_app.selectors import get_calendar_items, visible_events
from calendar_app.services import create_event, transition_event, update_event
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Membership, Organization
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from white_label.services import authenticate_api_key

from .serializers import EventSerializer


def parse_range(request):
    try:
        start_date = datetime.fromisoformat(request.query_params["start"])
        end_date = datetime.fromisoformat(request.query_params["end"])
    except (KeyError, ValueError) as exc:
        raise ValidationError("start and end must be ISO-8601 dates or datetimes.") from exc
    if timezone.is_naive(start_date):
        start_date = timezone.make_aware(datetime.combine(start_date.date(), time.min))
    if timezone.is_naive(end_date):
        end_date = timezone.make_aware(datetime.combine(end_date.date(), time.max))
    return start_date, end_date


def org_for(user, request):
    org_id = request.query_params.get("organization") or request.data.get("organization")
    if not org_id:
        raise ValidationError({"organization": "Organization is required."})
    return get_object_or_404(organizations_for_user(user), pk=org_id)


def filters(request):
    return {
        key: request.query_params.get(key)
        for key in ("artist", "source_type", "status", "priority")
        if request.query_params.get(key)
    }


def relation_data(data, org):
    artist_id = data.pop("artist", None)
    owner_id = data.pop("owner_membership", None)
    data["artist"] = (
        get_object_or_404(Artist, pk=artist_id, organization=org) if artist_id else None
    )
    data["owner_membership"] = (
        get_object_or_404(Membership.objects.active(), pk=owner_id, organization=org)
        if owner_id
        else None
    )
    return data


class CalendarView(APIView):
    def get(self, request):
        org = org_for(request.user, request)
        if not user_has_organization_permission(request.user, org, "calendar.view"):
            raise PermissionDenied()
        start, end = parse_range(request)
        try:
            return Response(get_calendar_items(request.user, org, start, end, filters(request)))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc


def _ics_text(value):
    slash = chr(92)
    return str(value or "").replace(slash, slash + slash).replace(";", slash + ";").replace(",", slash + ",").replace(chr(10), slash + "n").replace(chr(13), "")


def _ics_datetime(value):
    parsed = datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class CalendarExportView(APIView):
    def get(self, request):
        org = org_for(request.user, request)
        if not user_has_organization_permission(request.user, org, "calendar.view"):
            raise PermissionDenied()
        try:
            start, end = parse_range(request) if request.query_params.get("start") and request.query_params.get("end") else (
                timezone.now(),
                timezone.now() + timedelta(days=366),
            )
            items = get_calendar_items(request.user, org, start, end, filters(request))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Evolve//Operations Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Evolve Calendar",
        ]
        for item in items:
            start_value = _ics_datetime(item["starts_at"])
            end_value = _ics_datetime(item["ends_at"]) if item.get("ends_at") else start_value
            url = item.get("url") or "/workspace/calendar"
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{_ics_text(item['id'])}@evolve.nastycsa.com",
                f"DTSTAMP:{timezone.now().astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{start_value}",
                f"DTEND:{end_value}",
                f"SUMMARY:{_ics_text(item['title'])}",
                f"DESCRIPTION:{_ics_text(item.get('source_type', '') + ' / ' + item.get('status', ''))}",
                f"URL:https://evolve.nastycsa.com{url}",
                "END:VEVENT",
            ])
        lines.append("END:VCALENDAR")
        response = HttpResponse((chr(13) + chr(10)).join(lines) + chr(13) + chr(10), content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="evolve-calendar.ics"'
        return response


class EventListView(APIView):
    def get(self, request):
        org = org_for(request.user, request)
        if not user_has_organization_permission(request.user, org, "calendar.view"):
            raise PermissionDenied()
        return Response(EventSerializer(visible_events(request.user, org), many=True).data)

    def post(self, request):
        org = org_for(request.user, request)
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            event = create_event(
                actor=request.user,
                organization=org,
                request=request,
                **relation_data(serializer.validated_data, org),
            )
        except (PermissionError, ValueError) as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(EventSerializer(event).data, status=201)


class EventDetailView(APIView):
    def get_object(self, request, event_id):
        org = org_for(request.user, request)
        return get_object_or_404(visible_events(request.user, org), pk=event_id)

    def get(self, request, event_id):
        return Response(EventSerializer(self.get_object(request, event_id)).data)

    def patch(self, request, event_id):
        event = self.get_object(request, event_id)
        serializer = EventSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            event = update_event(
                event,
                actor=request.user,
                request=request,
                **relation_data(serializer.validated_data, event.organization),
            )
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        return Response(EventSerializer(event).data)


class EventStatusView(APIView):
    def post(self, request, event_id):
        org = org_for(request.user, request)
        event = get_object_or_404(visible_events(request.user, org), pk=event_id)
        try:
            event = transition_event(
                event, request.data.get("status"), actor=request.user, request=request
            )
        except (PermissionError, ValueError) as exc:
            raise ValidationError(str(exc)) from exc
        return Response(EventSerializer(event).data)


class PortalCalendarView(APIView):
    def get(self, request):
        org = org_for(request.user, request)
        start, end = parse_range(request)
        try:
            return Response(
                get_calendar_items(request.user, org, start, end, filters(request), portal=True)
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc


class PlatformCalendarView(APIView):
    permission_classes = [PlatformSuperuser]

    def get(self, request):
        org = get_object_or_404(Organization, pk=request.query_params.get("organization"))
        start, end = parse_range(request)
        try:
            return Response(get_calendar_items(request.user, org, start, end, filters(request)))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc


class DeveloperCalendarView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied()
        key = authenticate_api_key(header[7:], required_scope="calendar.read")
        start, end = parse_range(request)
        items = get_calendar_items(None, key.client.organization, start, end, filters(request))
        return Response(
            [
                {
                    k: item[k]
                    for k in (
                        "source_type",
                        "source_id",
                        "title",
                        "starts_at",
                        "ends_at",
                        "all_day",
                        "artist",
                        "status",
                    )
                }
                for item in items
                if item["source_type"] != "calendar_event" or item["status"] == "active"
            ]
        )
