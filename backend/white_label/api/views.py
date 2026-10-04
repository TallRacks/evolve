from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser

from audit.services import record_event
from organizations.api.permissions import PlatformSuperuser
from organizations.models import Organization
from organizations.selectors import organizations_for_user
from white_label.models import APIClient, APIKey, GlobalBranding, GlobalBrandingAsset, OrganizationBranding, OrganizationDomain
from documents.models import Document
from documents.services import upload_document
from documents.storage import DocumentStorageUnavailable, get_storage_backend
from white_label.services import (
    ALLOWED_SCOPES,
    authenticate_api_key,
    create_api_client_key,
    create_domain,
    effective_branding,
    effective_global_branding,
    organization_for_host,
    require_manage,
    verify_domain,
    upload_global_branding_asset,
)

from .serializers import (
    APIClientCreateSerializer,
    APIClientSerializer,
    BrandingSerializer,
    DomainSerializer,
    GlobalBrandingSerializer,
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
            return Response({"organization_id": None, **effective_global_branding()})
        organization = scoped_organization(request.user, organization_id)
        return Response({"organization_id": organization.id, **effective_branding(organization)})


class PublicBrandingAssetView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, asset_type):
        if asset_type not in {GlobalBrandingAsset.AssetType.LOGO, GlobalBrandingAsset.AssetType.DARK_LOGO, GlobalBrandingAsset.AssetType.FAVICON, GlobalBrandingAsset.AssetType.MOBILE_ICON}:
            raise PermissionDenied("Asset type must be logo or favicon.")
        branding = get_object_or_404(GlobalBranding, assets__asset_type=asset_type)
        asset = get_object_or_404(GlobalBrandingAsset, branding=branding, asset_type=asset_type)
        try:
            stored = get_storage_backend(asset.storage_provider).open_stream(asset.storage_key)
        except DocumentStorageUnavailable as error:
            raise PermissionDenied(str(error)) from error

        def stream():
            try:
                while chunk := stored.body.read(64 * 1024):
                    yield chunk
            finally:
                close = getattr(stored.body, "close", None)
                if close:
                    close()

        response = StreamingHttpResponse(stream(), content_type=asset.content_type)
        response["Content-Disposition"] = f'inline; filename="{asset.original_filename}"'
        response["Cache-Control"] = "public, max-age=300"
        response["X-Content-Type-Options"] = "nosniff"
        if stored.content_length:
            response["Content-Length"] = stored.content_length
        return response


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


class OrganizationBrandingAssetView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, organization_id):
        organization = scoped_organization(request.user, organization_id)
        require_manage(request.user, organization, "branding.manage")
        asset_type = request.data.get("asset_type")
        if asset_type not in {"logo", "favicon", "mobile_icon"}:
            raise PermissionDenied("Asset type must be logo or favicon.")
        file = request.FILES.get("file")
        if not file:
            raise PermissionDenied("Choose an image file.")
        if not str(file.content_type or "").lower().startswith(("image/png", "image/jpeg", "image/webp")):
            raise PermissionDenied("Brand assets must be PNG, JPEG, or WebP images.")
        try:
            document = upload_document(actor=request.user, organization=organization, file=file, request=request, title="Brand " + asset_type, document_type=Document.Type.ARTWORK, visibility=Document.Visibility.ORGANIZATION)
        except DocumentStorageUnavailable as error:
            raise PermissionDenied(str(error)) from error
        url = request.build_absolute_uri("/api/documents/" + str(document.pk) + "/preview/?organization=" + str(organization.pk))
        branding, _ = OrganizationBranding.objects.get_or_create(organization=organization)
        setattr(branding, asset_type + "_url", url)
        branding.save(update_fields=(asset_type + "_url", "updated_at"))
        record_event(actor=request.user, organization=organization, action="branding." + asset_type + "_uploaded", resource=branding, description="Uploaded organization " + asset_type + ".", request=request)
        return Response(BrandingSerializer(branding).data)
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


class GlobalBrandingView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request):
        branding = GlobalBranding.objects.first()
        if branding is None:
            branding = GlobalBranding()
        return Response(GlobalBrandingSerializer(branding).data)

    def patch(self, request):
        branding, _ = GlobalBranding.objects.get_or_create()
        serializer = GlobalBrandingSerializer(branding, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_event(actor=request.user, action="branding.global_updated", resource=branding, description="Updated global platform branding.", request=request)
        return Response(serializer.data)


class GlobalBrandingAssetView(APIView):
    permission_classes = (PlatformSuperuser,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        branding, _ = GlobalBranding.objects.get_or_create()
        asset_type = request.data.get("asset_type")
        file = request.FILES.get("file")
        if not file:
            raise PermissionDenied("Choose an image file.")
        try:
            upload_global_branding_asset(
                actor=request.user, branding=branding, asset_type=asset_type,
                file=file, request=request,
            )
        except DjangoValidationError as error:
            raise PermissionDenied(getattr(error, "message", error.messages)) from error
        except DocumentStorageUnavailable as error:
            raise PermissionDenied(str(error)) from error
        return Response(GlobalBrandingSerializer(branding).data)


class GlobalBrandingAssetPreviewView(APIView):
    permission_classes = (PlatformSuperuser,)

    def get(self, request, asset_type):
        if asset_type not in {GlobalBrandingAsset.AssetType.LOGO, GlobalBrandingAsset.AssetType.DARK_LOGO, GlobalBrandingAsset.AssetType.FAVICON, GlobalBrandingAsset.AssetType.MOBILE_ICON}:
            raise PermissionDenied("Asset type must be logo or favicon.")
        branding = get_object_or_404(GlobalBranding, assets__asset_type=asset_type)
        asset = get_object_or_404(
            GlobalBrandingAsset, branding=branding, asset_type=asset_type
        )
        try:
            stored = get_storage_backend(asset.storage_provider).open_stream(asset.storage_key)
        except DocumentStorageUnavailable as error:
            raise PermissionDenied(str(error)) from error

        def stream():
            try:
                while chunk := stored.body.read(64 * 1024):
                    yield chunk
            finally:
                close = getattr(stored.body, "close", None)
                if close:
                    close()

        response = StreamingHttpResponse(stream(), content_type=asset.content_type)
        response["Content-Disposition"] = f'inline; filename="{asset.original_filename}"'
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        if stored.content_length:
            response["Content-Length"] = stored.content_length
        record_event(
            actor=request.user, action="branding.global_asset_previewed", resource=branding,
            description=f"Previewed global {asset_type} asset.", request=request,
        )
        return response


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
