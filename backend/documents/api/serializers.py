from rest_framework import serializers

from documents.models import Document, DocumentLink


class LinkSerializer(serializers.ModelSerializer):
    entity_type = serializers.CharField(read_only=True)
    entity_id = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()

    class Meta:
        model = DocumentLink
        fields = (
            "id",
            "entity_type",
            "entity_id",
            "label",
            "artist",
            "booking",
            "call_sheet",
            "release",
            "campaign",
            "travel_itinerary",
            "travel_segment",
            "accommodation_stay",
            "production_advance",
            "created_at",
        )

    def get_entity_id(self, obj):
        return str(obj.entity.pk)

    def get_label(self, obj):
        return str(obj.entity)


class SafeDocumentFieldsMixin(serializers.Serializer):
    checksum = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()

    def get_checksum(self, obj):
        return f"{obj.checksum_sha256[:12]}..." if obj.checksum_sha256 else ""

    def _url(self, obj, action):
        if obj.source_type != Document.SourceType.STORED:
            return None
        request = self.context.get("request")
        suffix = f"?organization={obj.organization_id}"
        path = f"/api/documents/{obj.pk}/{action}/{suffix}"
        return request.build_absolute_uri(path) if request else path

    def get_download_url(self, obj):
        return self._url(obj, "download")

    def get_preview_url(self, obj):
        inline_types = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
        if obj.detected_content_type not in inline_types:
            return None
        return self._url(obj, "preview")


class DocumentSerializer(SafeDocumentFieldsMixin, serializers.ModelSerializer):
    uploader = serializers.EmailField(source="uploaded_by.email", read_only=True)
    links = LinkSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "organization",
            "title",
            "document_type",
            "description",
            "source_type",
            "external_url",
            "rendered_content",
            "template",
            "template_version",
            "original_filename",
            "content_type",
            "detected_content_type",
            "file_size",
            "checksum",
            "storage_status",
            "download_url",
            "preview_url",
            "uploaded_at",
            "version_number",
            "parent_document",
            "visibility",
            "status",
            "uploader",
            "links",
            "created_at",
            "updated_at",
            "archived_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "source_type",
            "rendered_content",
            "template",
            "template_version",
            "detected_content_type",
            "checksum",
            "storage_status",
            "download_url",
            "preview_url",
            "uploaded_at",
            "version_number",
            "parent_document",
            "status",
            "uploader",
            "created_at",
            "updated_at",
            "archived_at",
        )

    def validate(self, attrs):
        if self.instance is None and not attrs.get("external_url"):
            raise serializers.ValidationError(
                {"external_url": "An HTTPS external reference is required."}
            )
        return attrs


class DocumentUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=220)
    document_type = serializers.ChoiceField(choices=Document.Type.choices)
    description = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    visibility = serializers.ChoiceField(
        choices=Document.Visibility.choices, default=Document.Visibility.ORGANIZATION
    )
    file = serializers.FileField()


class DocumentVersionUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    version_note = serializers.CharField(max_length=5000, required=False, allow_blank=True)


class PortalDocumentSerializer(SafeDocumentFieldsMixin, serializers.ModelSerializer):
    links = serializers.SerializerMethodField()

    def get_links(self, obj):
        return [
            {"entity_type": "artist", "entity_id": str(link.artist_id), "label": str(link.artist)}
            for link in obj.links.all()
            if link.artist_id
        ]

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "document_type",
            "source_type",
            "external_url",
            "original_filename",
            "content_type",
            "detected_content_type",
            "file_size",
            "version_number",
            "visibility",
            "status",
            "storage_status",
            "download_url",
            "preview_url",
            "links",
            "updated_at",
        )


class PlatformDocumentSummarySerializer(SafeDocumentFieldsMixin, serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    links = LinkSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "organization",
            "organization_name",
            "title",
            "document_type",
            "source_type",
            "version_number",
            "visibility",
            "status",
            "storage_status",
            "original_filename",
            "file_size",
            "download_url",
            "preview_url",
            "updated_at",
            "links",
        )


class DeveloperDocumentSerializer(serializers.ModelSerializer):
    linked_entities = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "document_type",
            "source_type",
            "version_number",
            "status",
            "linked_entities",
        )

    def get_linked_entities(self, obj):
        return [
            {"type": link.entity_type, "id": str(link.entity.pk), "label": str(link.entity)}
            for link in obj.links.all()
        ]
