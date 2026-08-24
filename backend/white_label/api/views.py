from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_event
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.selectors import organizations_for_user
from white_label.models import APIClient, APIKey, OrganizationBranding, OrganizationDomain
from white_label.services import (
    ALLOWED_SCOPES,
    authenticate_api_key,
    create_api_client_key,
    create_domain,
    effective_branding,
    organization_for_host,
    require_manage,
    verify_domain,
)

from .serializers import (
    APIClientCreateSerializer,
    APIClientSerializer,
    BrandingSerializer,
    DomainSerializer,
)


def scoped_organization(user, organization_id):
    return get_object_or_404(
        Organization.objects.filter(pk__in=organizations_for_user(user).values("pk")),
        pk=organization_id,
    )


class CurrentBrandingView(APIView):
    def get(self, request):
        organization_id = request.query_params.get("organization_id")
        if not organization_id:
            host_organization = organization_for_host(request.get_host())
            if host_organization:
                organization_id = host_organization.pk
        if not organization_id:
            organization_id = (
                organizations_for_user(request.user).values_list("pk", flat=True).first()
            )
        if not organization_id:
            raise PermissionDenied("Select an organization.")
        organization = scoped_organization(request.user, organization_id)
        return Response({"organization_id": organization.id, **effective_branding(organization)})


class OrganizationBrandingView(APIView):
    def get(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        branding = OrganizationBranding.objects.filter(organization=organization).first()
        if branding is None:
            branding = OrganizationBranding(organization=organization)
        return Response(BrandingSerializer(branding).data)

    def patch(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_manage(request.user, organization, "branding.manage")
        branding, _ = OrganizationBranding.objects.get_or_create(organization=organization)
        serializer = BrandingSerializer(branding, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_event(
            actor=request.user,
            organization=organization,
            action="branding.updated",
            resource=branding,
            description=f"Updated branding for {organization.name}.",
            request=request,
        )
        return Response(serializer.data)


class OrganizationDomainListView(APIView):
    def get(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_manage(request.user, organization, "domain.manage")
        return Response(DomainSerializer(organization.domains.all(), many=True).data)

    def post(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_manage(request.user, organization, "domain.manage")
        serializer = DomainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        domain = create_domain(
            organization=organization, hostname=serializer.validated_data["hostname"]
        )
        record_event(
            actor=request.user,
            organization=organization,
            action="domain.created",
            resource=domain,
            description=f"Created domain configuration for {domain.hostname}.",
            request=request,
        )
        record_event(
            actor=request.user,
            organization=organization,
            action="domain.verification_requested",
            resource=domain,
            description=f"Requested verification for {domain.hostname}.",
            request=request,
        )
        return Response(DomainSerializer(domain).data, status=status.HTTP_201_CREATED)


class PlatformBrandingListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        data = []
        for organization in Organization.objects.all():
            branding = OrganizationBranding.objects.filter(organization=organization).first()
            data.append(
                {
                    "organization": {"id": organization.id, "name": organization.name},
                    "configured": branding is not None,
                    "effective": effective_branding(organization),
                }
            )
        return Response(data)


class PlatformDomainListView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        return Response(
            DomainSerializer(
                OrganizationDomain.objects.select_related("organization"), many=True
            ).data
        )


class PlatformDomainDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def patch(self, request, domain_id):
        domain = get_object_or_404(OrganizationDomain, pk=domain_id)
        action = request.data.get("action")
        if action == "verify":
            verify_domain(domain)
            event_action = "domain.verified"
        elif action in {"activate", "deactivate"}:
            if (
                action == "activate"
                and domain.verification_status != OrganizationDomain.VerificationStatus.VERIFIED
            ):
                raise PermissionDenied("Only verified domains can be activated.")
            domain.is_active = action == "activate"
            domain.is_primary = domain.is_active and bool(request.data.get("is_primary", False))
            domain.full_clean()
            domain.save(update_fields=("is_active", "is_primary", "updated_at"))
            event_action = f"domain.{action}d"
        else:
            raise PermissionDenied("Unsupported domain action.")
        record_event(
            actor=request.user,
            organization=domain.organization,
            action=event_action,
            resource=domain,
            description=f"Updated domain {domain.hostname}.",
            request=request,
        )
        return Response(DomainSerializer(domain).data)


class APIClientListView(APIView):
    def get(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_manage(request.user, organization, "api.manage")
        clients = organization.api_clients.prefetch_related("keys")
        return Response(APIClientSerializer(clients, many=True).data)

    def post(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_manage(request.user, organization, "api.manage")
        serializer = APIClientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client, created = create_api_client_key(
            organization=organization, created_by=request.user, **serializer.validated_data
        )
        record_event(
            actor=request.user,
            organization=organization,
            action="api.client_created",
            resource=client,
            description=f"Created API client {client.name}.",
            request=request,
        )
        record_event(
            actor=request.user,
            organization=organization,
            action="api.key_created",
            resource=created.key,
            description=f"Created API key {created.key.key_prefix}.",
            request=request,
        )
        return Response(
            {**APIClientSerializer(client).data, "secret": created.secret},
            status=status.HTTP_201_CREATED,
        )


class APIKeyRevokeView(APIView):
    def post(self, request, organization_id, key_id):
        organization = scoped_organization(request.user, organization_id)
        require_manage(request.user, organization, "api.manage")
        key = get_object_or_404(
            APIKey.objects.select_related("client"), pk=key_id, client__organization=organization
        )
        if key.revoked_at is None:
            key.revoked_at = timezone.now()
            key.save(update_fields=("revoked_at",))
            record_event(
                actor=request.user,
                organization=organization,
                action="api.key_revoked",
                resource=key,
                description=f"Revoked API key {key.key_prefix}.",
                request=request,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlatformBrandingDetailView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        branding = OrganizationBranding.objects.filter(organization=organization).first()
        if branding is None:
            branding = OrganizationBranding(organization=organization)
        return Response(BrandingSerializer(branding).data)

    def patch(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        branding, _ = OrganizationBranding.objects.get_or_create(organization=organization)
        serializer = BrandingSerializer(branding, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_event(
            actor=request.user,
            organization=organization,
            action="branding.updated",
            resource=branding,
            description=f"Updated branding for {organization.name}.",
            request=request,
        )
        return Response(serializer.data)


class APIClientDetailView(APIView):
    def post(self, request, organization_id, client_id):
        organization = scoped_organization(request.user, organization_id)
        require_manage(request.user, organization, "api.manage")
        api_client = get_object_or_404(APIClient, pk=client_id, organization=organization)
        if api_client.is_active:
            api_client.is_active = False
            api_client.save(update_fields=("is_active", "updated_at"))
            record_event(
                actor=request.user,
                organization=organization,
                action="api.client_deactivated",
                resource=api_client,
                description=f"Deactivated API client {api_client.name}.",
                request=request,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeveloperMetadataView(APIView):
    def get(self, request):
        return Response(
            {
                "base_url": "https://evolve.nastycsa.com/api/",
                "scopes": ALLOWED_SCOPES,
                "rate_limiting": "Not yet implemented",
            }
        )


class DeveloperWhoAmIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise PermissionDenied("Invalid API credentials.")
        key = authenticate_api_key(header[7:], required_scope="organization.read")
        return Response(
            {
                "client": {"id": key.client_id, "name": key.client.name},
                "organization": {
                    "id": key.client.organization_id,
                    "name": key.client.organization.name,
                },
                "scopes": key.scopes,
            }
        )
