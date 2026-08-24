from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from contacts.models import Contact
from contacts.selectors import contacts_for_user
from contacts.services import create_contact, require_contact_permission, update_contact
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.selectors import organizations_for_user

from .serializers import ContactSerializer, ContactWriteSerializer


def queryset():
    return Contact.objects.select_related("organization").annotate(
        promoter_count=Count(
            "promoter_links", filter=Q(promoter_links__is_active=True), distinct=True
        ),
        venue_count=Count("venue_links", filter=Q(venue_links__is_active=True), distinct=True),
    )


def scoped_organization(user, organization_id):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")),
        pk=organization_id,
    )


def scoped_contact(user, contact_id):
    return get_object_or_404(
        queryset().filter(pk__in=contacts_for_user(user).values("pk")), pk=contact_id
    )


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
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(job_title__icontains=search)
        )
    active = request.query_params.get("is_active")
    if active in ("true", "false"):
        items = items.filter(is_active=active == "true")
    return items


class ContactListView(APIView):
    def get(self, request):
        organization = scoped_organization(
            request.user, request.query_params.get("organization_id")
        )
        require_contact_permission(request.user, organization, "contact.view")
        return Response(
            ContactSerializer(
                filtered(queryset().filter(organization=organization), request), many=True
            ).data
        )

    def post(self, request):
        organization = scoped_organization(request.user, request.data.get("organization_id"))
        require_contact_permission(request.user, organization, "contact.manage")
        serializer = ContactWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = validate(
            lambda: create_contact(
                actor=request.user,
                organization=organization,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            ContactSerializer(queryset().get(pk=contact.pk)).data, status=status.HTTP_201_CREATED
        )


class ContactDetailView(APIView):
    def get(self, request, contact_id):
        contact = scoped_contact(request.user, contact_id)
        require_contact_permission(request.user, contact.organization, "contact.view")
        data = ContactSerializer(contact).data
        data["promoters"] = [
            {
                "id": link.promoter_id,
                "name": link.promoter.name,
                "responsibility": link.responsibility,
                "is_primary": link.is_primary,
                "is_active": link.is_active,
            }
            for link in contact.promoter_links.select_related("promoter")
        ]
        data["venues"] = [
            {
                "id": link.venue_id,
                "name": link.venue.name,
                "responsibility": link.responsibility,
                "is_primary": link.is_primary,
                "is_active": link.is_active,
            }
            for link in contact.venue_links.select_related("venue")
        ]
        return Response(data)

    def patch(self, request, contact_id):
        contact = scoped_contact(request.user, contact_id)
        require_contact_permission(request.user, contact.organization, "contact.manage")
        serializer = ContactWriteSerializer(contact, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        contact = validate(
            lambda: update_contact(
                actor=request.user, contact=contact, data=serializer.validated_data, request=request
            )
        )
        return Response(ContactSerializer(queryset().get(pk=contact.pk)).data)


class PlatformContactListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(ContactSerializer(filtered(queryset(), request), many=True).data)

    def post(self, request):
        organization = get_object_or_404(Organization, pk=request.data.get("organization_id"))
        serializer = ContactWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = validate(
            lambda: create_contact(
                actor=request.user,
                organization=organization,
                data=serializer.validated_data,
                request=request,
            )
        )
        return Response(
            ContactSerializer(queryset().get(pk=contact.pk)).data, status=status.HTTP_201_CREATED
        )


class PlatformContactDetailView(ContactDetailView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, contact_id):
        return super().get(request, contact_id)
