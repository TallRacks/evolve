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
from venues.models import Venue, VenueContact
from venues.selectors import venue_activity, venues_for_user
from venues.services import (
    add_venue_contact,
    create_venue,
    require_venue_permission,
    update_venue,
    update_venue_contact,
)
from white_label.services import authenticate_api_key

from .serializers import (
    DeveloperVenueSerializer,
    VenueContactCreateSerializer,
    VenueContactSerializer,
    VenueSerializer,
    VenueWriteSerializer,
)


def queryset():
    return Venue.objects.select_related("organization").annotate(
        contact_count=Count("contact_links", filter=Q(contact_links__is_active=True), distinct=True)
    )


def scoped_org(user, pk):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")), pk=pk
    )


def scoped_venue(user, pk):
    return get_object_or_404(queryset().filter(pk__in=venues_for_user(user).values("pk")), pk=pk)


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
            Q(name__icontains=search) | Q(country__icontains=search) | Q(city__icontains=search)
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
        for event in venue_activity(obj)
    ]


class VenueListView(APIView):
    def get(self, request):
        org = scoped_org(request.user, request.query_params.get("organization_id"))
        require_venue_permission(request.user, org, "venue.view")
        return Response(
            VenueSerializer(filtered(queryset().filter(organization=org), request), many=True).data
        )

    def post(self, request):
        org = scoped_org(request.user, request.data.get("organization_id"))
        require_venue_permission(request.user, org, "venue.manage")
        serializer = VenueWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = validate(
            lambda: create_venue(
                actor=request.user,
                organization=org,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            VenueSerializer(queryset().get(pk=obj.pk)).data, status=status.HTTP_201_CREATED
        )


class VenueDetailView(APIView):
    def get(self, request, venue_id):
        obj = scoped_venue(request.user, venue_id)
        require_venue_permission(request.user, obj.organization, "venue.view")
        data = VenueSerializer(obj).data
        data["contacts"] = VenueContactSerializer(
            obj.contact_links.select_related("contact"), many=True
        ).data
        data["activity"] = activity(obj)
        return Response(data)

    def patch(self, request, venue_id):
        obj = scoped_venue(request.user, venue_id)
        require_venue_permission(request.user, obj.organization, "venue.manage")
        serializer = VenueWriteSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = validate(
            lambda: update_venue(
                actor=request.user, venue=obj, data=serializer.validated_data, request=request
            )
        )
        return Response(VenueSerializer(queryset().get(pk=obj.pk)).data)


class VenueContactsView(APIView):
    def get(self, request, venue_id):
        obj = scoped_venue(request.user, venue_id)
        require_venue_permission(request.user, obj.organization, "venue.view")
        return Response(
            VenueContactSerializer(obj.contact_links.select_related("contact"), many=True).data
        )

    def post(self, request, venue_id):
        obj = scoped_venue(request.user, venue_id)
        require_venue_permission(request.user, obj.organization, "venue.manage")
        serializer = VenueContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = get_object_or_404(
            Contact, pk=serializer.validated_data.pop("contact_id"), organization=obj.organization
        )
        link = validate(
            lambda: add_venue_contact(
                actor=request.user,
                venue=obj,
                contact=contact,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(VenueContactSerializer(link).data, status=status.HTTP_201_CREATED)


class VenueContactDetailView(APIView):
    def patch(self, request, venue_id, link_id):
        obj = scoped_venue(request.user, venue_id)
        require_venue_permission(request.user, obj.organization, "venue.manage")
        link = get_object_or_404(VenueContact, pk=link_id, venue=obj)
        serializer = VenueContactSerializer(link, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            VenueContactSerializer(
                validate(
                    lambda: update_venue_contact(
                        actor=request.user,
                        link=link,
                        data=serializer.validated_data,
                        request=request,
                    )
                )
            ).data
        )


class PlatformVenueListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(VenueSerializer(filtered(queryset(), request), many=True).data)

    def post(self, request):
        org = get_object_or_404(Organization, pk=request.data.get("organization_id"))
        serializer = VenueWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = validate(
            lambda: create_venue(
                actor=request.user,
                organization=org,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            VenueSerializer(queryset().get(pk=obj.pk)).data, status=status.HTTP_201_CREATED
        )


class PlatformVenueDetailView(VenueDetailView):
    permission_classes = (PlatformSuperuser,)


class DeveloperVenueListView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(header[7:], required_scope="venue.read")
        return Response(
            DeveloperVenueSerializer(
                filtered(Venue.objects.filter(organization=key.client.organization), request),
                many=True,
            ).data
        )
