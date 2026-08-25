from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.permissions import user_has_organization_permission
from organizations.selectors import organizations_for_user
from production.models import (
    AdvanceChecklistItem,
    AdvanceRequirement,
    ProductionContactAssignment,
    ProductionScheduleItem,
)
from production.selectors import (
    advance_activity,
    advance_queryset,
    advances_for_user,
    artist_advances_for_user,
)
from production.services import (
    REQUIREMENT_TRANSITIONS,
    SCHEDULE_TRANSITIONS,
    create_advance,
    create_child,
    deactivate_child,
    reorder_child,
    set_checklist_completion,
    transition_advance,
    transition_child,
    update_advance,
    update_child,
)
from white_label.services import authenticate_api_key

from .serializers import (
    AdvanceDetailSerializer,
    AdvanceListSerializer,
    AdvanceWriteSerializer,
    ArtistAdvanceSerializer,
    ChecklistSerializer,
    ContactAssignmentSerializer,
    DeveloperAdvanceSerializer,
    ReorderSerializer,
    RequirementSerializer,
    ScheduleSerializer,
    StatusSerializer,
)


def validation(call):
    try:
        return call()
    except DjangoValidationError as error:
        detail = error.message_dict if hasattr(error, "message_dict") else error.messages
        raise ValidationError(detail) from error


def scoped_organization(user, value):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")), pk=value
    )


def scoped_advance(user, pk):
    return get_object_or_404(advances_for_user(user), pk=pk)


def require(user, organization, permission="production.view"):
    if not user_has_organization_permission(user, organization, permission):
        raise PermissionDenied(
            "You do not have permission to access Production for this organization."
        )


def detail(row, user):
    activity = [
        {
            "id": x.id,
            "action": x.action,
            "description": x.description,
            "actor": x.actor.email if x.actor else None,
            "created_at": x.created_at,
        }
        for x in advance_activity(row)
    ]
    return AdvanceDetailSerializer(row, context={"activity": activity}).data


class AdvanceListView(APIView):
    def get(self, request):
        organization = scoped_organization(
            request.user, request.query_params.get("organization_id")
        )
        require(request.user, organization)
        rows = advances_for_user(request.user).filter(organization=organization)
        q = request.query_params.get("q", "").strip()
        if q:
            rows = rows.filter(
                Q(production_title__icontains=q)
                | Q(artist__stage_name__icontains=q)
                | Q(booking__reference__icontains=q)
                | Q(venue__name__icontains=q)
                | Q(promoter__name__icontains=q)
            )
        for param, field in (
            ("artist_id", "artist_id"),
            ("booking_id", "booking_id"),
            ("venue_id", "venue_id"),
            ("promoter_id", "promoter_id"),
            ("status", "status"),
        ):
            value = request.query_params.get(param)
            if value:
                rows = rows.filter(**{field: value})
        for param, lookup in (
            ("start", "booking__event_date__gte"),
            ("end", "booking__event_date__lte"),
        ):
            value = request.query_params.get(param)
            if value:
                parsed = parse_date(value)
                if not parsed:
                    raise ValidationError({param: "Enter a valid ISO date."})
                rows = rows.filter(**{lookup: parsed})
        if request.query_params.get("has_blocked_requirements") == "true":
            rows = rows.filter(requirements__status="blocked", requirements__is_active=True)
        rows = rows.distinct().order_by("booking__event_date", "production_title")
        try:
            offset = max(int(request.query_params.get("offset", 0)), 0)
        except (TypeError, ValueError) as error:
            raise ValidationError({"offset": "Enter a valid integer."}) from error
        count = rows.count()
        rows = rows[offset : offset + 50]
        return Response({"count": count, "results": AdvanceListSerializer(rows, many=True).data})

    def post(self, request):
        organization = scoped_organization(request.user, request.data.get("organization_id"))
        serializer = AdvanceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: create_advance(
                actor=request.user,
                organization=organization,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(detail(row, request.user), status=201)


class AdvanceDetailView(APIView):
    def get(self, request, advance_id):
        row = scoped_advance(request.user, advance_id)
        require(request.user, row.organization)
        return Response(detail(row, request.user))

    def patch(self, request, advance_id):
        row = scoped_advance(request.user, advance_id)
        serializer = AdvanceWriteSerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: update_advance(
                row, actor=request.user, data=serializer.validated_data, request=request
            )
        )
        return Response(detail(row, request.user))


class AdvanceStatusView(APIView):
    def post(self, request, advance_id):
        row = scoped_advance(request.user, advance_id)
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: transition_advance(
                row,
                actor=request.user,
                to_status=serializer.validated_data["to_status"],
                request=request,
            )
        )
        return Response(detail(row, request.user))


CONFIG = {
    "requirement": (
        AdvanceRequirement,
        RequirementSerializer,
        "production.requirements.manage",
        "production.requirement",
    ),
    "contact": (
        ProductionContactAssignment,
        ContactAssignmentSerializer,
        "production.contacts.manage",
        "production.contact",
    ),
    "schedule": (
        ProductionScheduleItem,
        ScheduleSerializer,
        "production.schedule.manage",
        "production.schedule",
    ),
    "checklist": (
        AdvanceChecklistItem,
        ChecklistSerializer,
        "production.checklist.manage",
        "production.checklist",
    ),
}


class ChildListView(APIView):
    kind = None

    def post(self, request, advance_id):
        row = scoped_advance(request.user, advance_id)
        model, serializer_class, permission, prefix = CONFIG[self.kind]
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = validation(
            lambda: create_child(
                model,
                row,
                actor=request.user,
                data=serializer.validated_data,
                permission=permission,
                action=f"{prefix}_{'assigned' if self.kind == 'contact' else 'created'}",
                request=request,
            )
        )
        return Response(serializer_class(child).data, status=201)


class ChildDetailView(APIView):
    kind = None

    def get_row(self, user, pk):
        model = CONFIG[self.kind][0]
        return get_object_or_404(
            model.objects.select_related("advance__organization").filter(
                advance__in=advances_for_user(user)
            ),
            pk=pk,
        )

    def patch(self, request, child_id):
        row = self.get_row(request.user, child_id)
        model, serializer_class, permission, prefix = CONFIG[self.kind]
        serializer = serializer_class(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: update_child(
                row,
                actor=request.user,
                data=serializer.validated_data,
                permission=permission,
                action=f"{prefix}_updated",
                request=request,
            )
        )
        return Response(serializer_class(row).data)

    def delete(self, request, child_id):
        row = self.get_row(request.user, child_id)
        _, _, permission, prefix = CONFIG[self.kind]
        validation(
            lambda: deactivate_child(
                row,
                actor=request.user,
                permission=permission,
                action=f"{prefix}_removed",
                request=request,
            )
        )
        return Response(status=204)


class ChildStatusView(ChildDetailView):
    def post(self, request, child_id):
        row = self.get_row(request.user, child_id)
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if self.kind == "requirement":
            transitions, permission, action = (
                REQUIREMENT_TRANSITIONS,
                "production.requirements.manage",
                "production.requirement_status_changed",
            )
        else:
            transitions, permission, action = (
                SCHEDULE_TRANSITIONS,
                "production.schedule.manage",
                "production.schedule_status_changed",
            )
        row = validation(
            lambda: transition_child(
                row,
                actor=request.user,
                to_status=serializer.validated_data["to_status"],
                permission=permission,
                transitions=transitions,
                action=action,
                request=request,
            )
        )
        return Response(CONFIG[self.kind][1](row).data)


class ChildReorderView(ChildDetailView):
    def post(self, request, child_id):
        row = self.get_row(request.user, child_id)
        serializer = ReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = validation(
            lambda: reorder_child(
                row,
                actor=request.user,
                direction=serializer.validated_data["direction"],
                permission=CONFIG[self.kind][2],
                action=f"{CONFIG[self.kind][3]}_updated",
                request=request,
            )
        )
        return Response(CONFIG[self.kind][1](row).data)


class ChecklistCompletionView(ChildDetailView):
    kind = "checklist"
    completed = True

    def post(self, request, child_id):
        row = self.get_row(request.user, child_id)
        row = validation(
            lambda: set_checklist_completion(
                row, actor=request.user, completed=self.completed, request=request
            )
        )
        return Response(ChecklistSerializer(row).data)


class ArtistProductionView(APIView):
    def get(self, request):
        return Response(
            ArtistAdvanceSerializer(artist_advances_for_user(request.user), many=True).data
        )


class PlatformAdvanceListView(APIView):
    permission_classes = [IsAuthenticated, PlatformSuperuser]

    def get(self, request):
        rows = advance_queryset()
        for param, field in (
            ("organization_id", "organization_id"),
            ("artist_id", "artist_id"),
            ("booking_id", "booking_id"),
            ("venue_id", "venue_id"),
            ("status", "status"),
        ):
            value = request.query_params.get(param)
            if value:
                rows = rows.filter(**{field: value})
        return Response(AdvanceListSerializer(rows[:200], many=True).data)


class PlatformAdvanceDetailView(APIView):
    permission_classes = [IsAuthenticated, PlatformSuperuser]

    def get(self, request, advance_id):
        return Response(detail(get_object_or_404(advance_queryset(), pk=advance_id), request.user))


class DeveloperProductionView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise PermissionDenied("API credentials are required.")
        key = authenticate_api_key(authorization[7:], "production.read")
        rows = (
            advance_queryset()
            .filter(organization=key.client.organization)
            .exclude(status="archived")
        )
        return Response({"results": DeveloperAdvanceSerializer(rows, many=True).data})
