from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Contact
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.selectors import organizations_for_user
from promoters.models import Promoter, PromoterContact
from promoters.selectors import promoter_activity, promoters_for_user
from promoters.services import (
    add_promoter_contact,
    create_promoter,
    require_promoter_permission,
    update_promoter,
    update_promoter_contact,
)
from white_label.services import authenticate_api_key

from .serializers import (
    DeveloperPromoterSerializer,
    PromoterContactCreateSerializer,
    PromoterContactSerializer,
    PromoterSerializer,
    PromoterWriteSerializer,
)


def queryset():
    return Promoter.objects.select_related("organization").annotate(
        contact_count=Count("contact_links", filter=Q(contact_links__is_active=True), distinct=True)
    )


def scoped_org(user, pk):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")), pk=pk
    )


def scoped_promoter(user, pk):
    return get_object_or_404(queryset().filter(pk__in=promoters_for_user(user).values("pk")), pk=pk)


def validate(call):
    try:
        return call()
    except DjangoValidationError as error:
        raise ValidationError(
            error.message_dict if hasattr(error, "message_dict") else error.messages
        ) from error


def filtered(items, request):
    search = request.query_params.get("search", "").strip()
    if search:
        items = items.filter(
            Q(name__icontains=search)
            | Q(company_name__icontains=search)
            | Q(city__icontains=search)
        )
    if request.query_params.get("status"):
        items = items.filter(status=request.query_params["status"])
    if request.query_params.get("organization_id"):
        items = items.filter(organization_id=request.query_params["organization_id"])
    return items


def activity(obj):
    return [
        {
            "id": event.id,
            "action": event.action,
            "description": event.description,
            "actor": event.actor.email if event.actor else None,
            "created_at": event.created_at,
        }
        for event in promoter_activity(obj)
    ]


class PromoterListView(APIView):
    def get(self, request):
        org = scoped_org(request.user, request.query_params.get("organization_id"))
        require_promoter_permission(request.user, org, "promoter.view")
        return Response(
            PromoterSerializer(
                filtered(queryset().filter(organization=org), request), many=True
            ).data
        )

    def post(self, request):
        org = scoped_org(request.user, request.data.get("organization_id"))
        require_promoter_permission(request.user, org, "promoter.manage")
        serializer = PromoterWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = validate(
            lambda: create_promoter(
                actor=request.user,
                organization=org,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            PromoterSerializer(queryset().get(pk=obj.pk)).data, status=status.HTTP_201_CREATED
        )


class PromoterDetailView(APIView):
    def get(self, request, promoter_id):
        obj = scoped_promoter(request.user, promoter_id)
        require_promoter_permission(request.user, obj.organization, "promoter.view")
        data = PromoterSerializer(obj).data
        data["contacts"] = PromoterContactSerializer(
            obj.contact_links.select_related("contact"), many=True
        ).data
        data["activity"] = activity(obj)
        return Response(data)

    def patch(self, request, promoter_id):
        obj = scoped_promoter(request.user, promoter_id)
        require_promoter_permission(request.user, obj.organization, "promoter.manage")
        serializer = PromoterWriteSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = validate(
            lambda: update_promoter(
                actor=request.user, promoter=obj, data=serializer.validated_data, request=request
            )
        )
        return Response(PromoterSerializer(queryset().get(pk=obj.pk)).data)


class PromoterContactsView(APIView):
    def get(self, request, promoter_id):
        obj = scoped_promoter(request.user, promoter_id)
        require_promoter_permission(request.user, obj.organization, "promoter.view")
        return Response(
            PromoterContactSerializer(obj.contact_links.select_related("contact"), many=True).data
        )

    def post(self, request, promoter_id):
        obj = scoped_promoter(request.user, promoter_id)
        require_promoter_permission(request.user, obj.organization, "promoter.manage")
        serializer = PromoterContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = get_object_or_404(
            Contact, pk=serializer.validated_data.pop("contact_id"), organization=obj.organization
        )
        link = validate(
            lambda: add_promoter_contact(
                actor=request.user,
                promoter=obj,
                contact=contact,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(PromoterContactSerializer(link).data, status=status.HTTP_201_CREATED)


class PromoterContactDetailView(APIView):
    def patch(self, request, promoter_id, link_id):
        obj = scoped_promoter(request.user, promoter_id)
        require_promoter_permission(request.user, obj.organization, "promoter.manage")
        link = get_object_or_404(PromoterContact, pk=link_id, promoter=obj)
        serializer = PromoterContactSerializer(link, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            PromoterContactSerializer(
                validate(
                    lambda: update_promoter_contact(
                        actor=request.user,
                        link=link,
                        data=serializer.validated_data,
                        request=request,
                    )
                )
            ).data
        )


class PlatformPromoterListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(PromoterSerializer(filtered(queryset(), request), many=True).data)

    def post(self, request):
        org = get_object_or_404(Organization, pk=request.data.get("organization_id"))
        serializer = PromoterWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = validate(
            lambda: create_promoter(
                actor=request.user,
                organization=org,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            PromoterSerializer(queryset().get(pk=obj.pk)).data, status=status.HTTP_201_CREATED
        )


class PlatformPromoterDetailView(PromoterDetailView):
    permission_classes = (PlatformSuperuser,)


class DeveloperPromoterListView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(header[7:], required_scope="promoter.read")
        return Response(
            DeveloperPromoterSerializer(
                filtered(Promoter.objects.filter(organization=key.client.organization), request),
                many=True,
            ).data
        )
