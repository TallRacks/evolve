from rest_framework import serializers

from promoters.models import Promoter, PromoterContact


class PromoterSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    contact_count = serializers.IntegerField(read_only=True)
    primary_contact = serializers.SerializerMethodField()

    class Meta:
        model = Promoter
        fields = (
            "id",
            "organization",
            "name",
            "company_name",
            "slug",
            "status",
            "website",
            "email",
            "phone",
            "address_line_1",
            "address_line_2",
            "city",
            "province",
            "postal_code",
            "country",
            "notes",
            "contact_count",
            "primary_contact",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "contact_count",
            "primary_contact",
            "created_at",
            "updated_at",
        )

    def get_organization(self, obj):
        return {"id": obj.organization_id, "name": obj.organization.name}

    def get_primary_contact(self, obj):
        link = (
            obj.contact_links.filter(is_active=True, is_primary=True)
            .select_related("contact")
            .first()
        )
        return (
            None
            if not link
            else {
                "id": link.contact_id,
                "name": link.contact.full_name,
                "email": link.contact.email,
            }
        )


class PromoterWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promoter
        fields = (
            "name",
            "company_name",
            "slug",
            "status",
            "website",
            "email",
            "phone",
            "address_line_1",
            "address_line_2",
            "city",
            "province",
            "postal_code",
            "country",
            "notes",
        )


class PromoterContactSerializer(serializers.ModelSerializer):
    contact = serializers.SerializerMethodField()

    class Meta:
        model = PromoterContact
        fields = (
            "id",
            "contact",
            "responsibility",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "contact", "created_at", "updated_at")

    def get_contact(self, link):
        return {
            "id": link.contact_id,
            "name": link.contact.full_name,
            "job_title": link.contact.job_title,
            "email": link.contact.email,
            "phone": link.contact.phone,
        }


class PromoterContactCreateSerializer(serializers.Serializer):
    contact_id = serializers.UUIDField()
    responsibility = serializers.ChoiceField(choices=PromoterContact.Responsibility.choices)
    is_primary = serializers.BooleanField(default=False)


class DeveloperPromoterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promoter
        fields = (
            "id",
            "name",
            "company_name",
            "slug",
            "status",
            "website",
            "city",
            "country",
            "updated_at",
        )
