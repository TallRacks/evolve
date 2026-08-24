from rest_framework import serializers

from contacts.models import Contact


class ContactSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    promoter_count = serializers.IntegerField(read_only=True)
    venue_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Contact
        fields = (
            "id",
            "organization",
            "first_name",
            "last_name",
            "job_title",
            "email",
            "phone",
            "mobile",
            "notes",
            "is_active",
            "promoter_count",
            "venue_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "promoter_count",
            "venue_count",
            "created_at",
            "updated_at",
        )

    def get_organization(self, contact):
        return {"id": contact.organization_id, "name": contact.organization.name}


class ContactWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = (
            "first_name",
            "last_name",
            "job_title",
            "email",
            "phone",
            "mobile",
            "notes",
            "is_active",
        )
