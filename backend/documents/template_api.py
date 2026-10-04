import secrets
from pathlib import PurePath

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.selectors import bookings_for_user
from documents.file_validation import validate_upload
from documents.models import DocumentTemplate, DocumentTemplateSection
from documents.storage import (
    DocumentStorageUnavailable,
    default_storage_provider,
    ensure_storage_key,
    get_storage_backend,
)
from documents.template_services import (
    add_template_section,
    booking_context,
    bootstrap_templates,
    create_template,
    duplicate_template,
    generate_booking_document,
    render_template,
    require_template_permission,
    set_template_default,
    set_template_status,
    update_template,
    update_template_section,
)
from documents.template_validation import ALLOWED_VARIABLES, validate_template_text
from organizations.selectors import organizations_for_user
from white_label.services import effective_branding


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplateSection
        fields = ("id", "key", "title", "body", "sequence", "is_enabled")
        read_only_fields = ("id",)

    def validate(self, attrs):
        validate_template_text(attrs.get("title", getattr(self.instance, "title", "")))
        validate_template_text(attrs.get("body", getattr(self.instance, "body", "")))
        return attrs


class TemplateSerializer(serializers.ModelSerializer):
    sections = SectionSerializer(many=True, read_only=True)
    variables = serializers.SerializerMethodField()

    class Meta:
        model = DocumentTemplate
        fields = (
            "id",
            "organization",
            "name",
            "key",
            "document_type",
            "description",
            "branding",
            "category",
            "status",
            "version",
            "sections",
            "variables",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "status",
            "version",
            "sections",
            "variables",
            "created_at",
            "updated_at",
        )

    def get_variables(self, template):
        return sorted(ALLOWED_VARIABLES)


def organization_for_request(request):
    organization_id = request.query_params.get("organization_id") or request.data.get(
        "organization_id"
    )
    return get_object_or_404(organizations_for_user(request.user), pk=organization_id)


def available_templates(user, organization):
    queryset = DocumentTemplate.objects.filter(
        Q(organization=organization) | Q(organization__isnull=True)
    ).prefetch_related("sections")
    if not user.is_superuser:
        try:
            require_template_permission(user, organization, "document_template.view")
        except PermissionDenied:
            return queryset.none()
    return queryset


class TemplateAPIView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            exc = ValidationError(detail)
        return super().handle_exception(exc)


class TemplateListView(TemplateAPIView):
    def get(self, request):
        organization = organization_for_request(request)
        return Response(
            TemplateSerializer(available_templates(request.user, organization), many=True).data
        )

    def post(self, request):
        organization = organization_for_request(request)
        serializer = TemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = create_template(
            actor=request.user,
            organization=organization,
            data=serializer.validated_data,
            request=request,
        )
        return Response(TemplateSerializer(template).data, status=201)


class TemplateDetailView(TemplateAPIView):
    def get_object(self, request, template_id):
        organization = organization_for_request(request)
        return get_object_or_404(available_templates(request.user, organization), pk=template_id)

    def get(self, request, template_id):
        return Response(TemplateSerializer(self.get_object(request, template_id)).data)

    def patch(self, request, template_id):
        template = self.get_object(request, template_id)
        if template.organization_id is None:
            raise PermissionDenied("Platform defaults cannot be edited from a workspace.")
        serializer = TemplateSerializer(template, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(
            TemplateSerializer(
                update_template(
                    actor=request.user,
                    template=template,
                    data=serializer.validated_data,
                    request=request,
                )
            ).data
        )


class TemplateSectionView(TemplateAPIView):
    def post(self, request, template_id):
        organization = organization_for_request(request)
        template = get_object_or_404(
            available_templates(request.user, organization),
            pk=template_id,
            organization=organization,
        )
        serializer = SectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = add_template_section(
            actor=request.user, template=template, data=serializer.validated_data
        )
        return Response(SectionSerializer(section).data, status=201)


class TemplateSectionDetailView(TemplateAPIView):
    def patch(self, request, template_id, section_id):
        organization = organization_for_request(request)
        template = get_object_or_404(
            available_templates(request.user, organization),
            pk=template_id,
            organization=organization,
        )
        section = get_object_or_404(template.sections, pk=section_id)
        serializer = SectionSerializer(section, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        section = update_template_section(
            actor=request.user,
            section=section,
            data=serializer.validated_data,
            request=request,
        )
        return Response(SectionSerializer(section).data)


class TemplateLogoUploadView(TemplateAPIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, template_id):
        organization = organization_for_request(request)
        template = get_object_or_404(available_templates(request.user, organization), pk=template_id, organization=organization)
        require_template_permission(request.user, organization, "document_template.manage")
        file = request.FILES.get("file")
        if not file:
            raise ValidationError("Choose a logo image.")
        metadata = validate_upload(file)
        if metadata["content_type"] not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValidationError("Template logos must be PNG, JPEG, or WebP images.")
        provider = default_storage_provider()
        suffix = PurePath(metadata["original_filename"]).suffix.lower()
        key = f"templates/{organization.pk}/{template.pk}/logo/{secrets.token_urlsafe(18)}{suffix}"
        ensure_storage_key(key)
        get_storage_backend(provider).put(key, file, metadata["content_type"], {"asset": "template_logo", "template": str(template.pk)})
        branding = dict(template.branding or {})
        branding.update({"logo_url": f"/api/document-templates/{template.pk}/branding/logo/preview/", "logo_storage_key": key, "logo_storage_provider_id": str(provider.pk), "logo_content_type": metadata["content_type"]})
        template.branding = branding
        template.version += 1
        template.save(update_fields=("branding", "version", "updated_at"))
        return Response(TemplateSerializer(template).data)


class TemplateLogoPreviewView(TemplateAPIView):
    def get(self, request, template_id):
        organization = organization_for_request(request)
        template = get_object_or_404(available_templates(request.user, organization), pk=template_id)
        branding = template.branding or {}
        key = branding.get("logo_storage_key")
        provider_id = branding.get("logo_storage_provider_id")
        if not key or not provider_id:
            raise PermissionDenied("This template has no uploaded logo.")
        from integrations.models import StorageProvider
        provider = get_object_or_404(StorageProvider, pk=provider_id)
        try:
            stored = get_storage_backend(provider).open_stream(key)
        except DocumentStorageUnavailable as error:
            raise PermissionDenied(str(error)) from error
        response = StreamingHttpResponse(stored.body, content_type=branding.get("logo_content_type", stored.content_type))
        response["Cache-Control"] = "private, max-age=300"
        return response


class TemplateActionView(TemplateAPIView):
    def post(self, request, template_id, action):
        organization = organization_for_request(request)
        template = get_object_or_404(
            available_templates(request.user, organization), pk=template_id
        )
        if action == "duplicate":
            template = duplicate_template(
                actor=request.user,
                template=template,
                organization=organization,
                key=request.data.get("key", f"{template.key}-copy"),
                request=request,
            )
        elif action == "set-default":
            template = set_template_default(actor=request.user, template=template, request=request)
        elif action in {"active", "inactive", "archive", "restore"}:
            if template.organization_id is None:
                raise PermissionDenied("Platform defaults cannot be changed from a workspace.")
            template = set_template_status(
                actor=request.user,
                template=template,
                status=(
                    "inactive"
                    if action == "archive"
                    else "active"
                    if action == "restore"
                    else action
                ),
                request=request,
            )
        else:
            return Response(status=404)
        return Response(TemplateSerializer(template).data)


class TemplateBootstrapView(TemplateAPIView):
    def post(self, request):
        organization = organization_for_request(request)
        templates = bootstrap_templates(actor=request.user, organization=organization, request=request)
        return Response(TemplateSerializer(templates, many=True).data, status=201)


class TemplatePreviewView(TemplateAPIView):
    def post(self, request, template_id):
        organization = organization_for_request(request)
        template = get_object_or_404(
            available_templates(request.user, organization), pk=template_id
        )
        booking = get_object_or_404(
            bookings_for_user(request.user),
            pk=request.data.get("booking_id"),
            organization=organization,
        )
        content, missing = render_template(template, booking_context(booking))
        branding = {**effective_branding(organization), **(template.branding or {})}
        branding["primary"] = branding.get("primary") or branding.get("primary_color", "")
        branding["accent"] = branding.get("accent") or branding.get("accent_color", "")
        return Response(
            {
                "content": content,
                "missing_variables": missing,
                "branding": {
                    key: branding.get(key, "")
                    for key in (
                        "brand_name",
                        "logo_url",
                        "primary",
                        "accent",
                        "text_primary",
                        "header_text",
                        "footer_text",
                    )
                },
            }
        )


class TemplateGenerateView(TemplateAPIView):
    def post(self, request, template_id):
        organization = organization_for_request(request)
        template = get_object_or_404(
            available_templates(request.user, organization), pk=template_id
        )
        booking = get_object_or_404(
            bookings_for_user(request.user),
            pk=request.data.get("booking_id"),
            organization=organization,
        )
        document, missing = generate_booking_document(
            actor=request.user,
            template=template,
            booking=booking,
            title=request.data.get("title") or f"{booking.reference} document",
            request=request,
        )
        return Response({"id": document.pk, "missing_variables": missing}, status=201)
