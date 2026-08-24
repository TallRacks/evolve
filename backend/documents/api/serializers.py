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
            "created_at",
        )

    def get_entity_id(self, obj):
        return str(obj.entity.pk)

    def get_label(self, obj):
        return str(obj.entity)


class DocumentSerializer(serializers.ModelSerializer):
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
            "external_url",
            "original_filename",
            "content_type",
            "file_size",
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


class PortalDocumentSerializer(serializers.ModelSerializer):
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
            "external_url",
            "original_filename",
            "content_type",
            "file_size",
            "version_number",
            "visibility",
            "status",
            "links",
            "updated_at",
        )


class PlatformDocumentSummarySerializer(serializers.ModelSerializer):
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
            "version_number",
            "visibility",
            "status",
            "original_filename",
            "updated_at",
            "links",
        )


class DeveloperDocumentSerializer(serializers.ModelSerializer):
    linked_entities = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ("id", "title", "document_type", "version_number", "status", "linked_entities")

    def get_linked_entities(self, obj):
        return [
            {"type": link.entity_type, "id": str(link.entity.pk), "label": str(link.entity)}
            for link in obj.links.all()
        ]
