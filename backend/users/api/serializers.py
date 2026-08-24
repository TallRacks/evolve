from rest_framework import serializers

from organizations.models import Membership


class ActiveMembershipSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "organization_id", "organization_name", "organization_slug", "role")


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    memberships = serializers.SerializerMethodField()

    def get_memberships(self, user):
        memberships = user.memberships.active().select_related("organization")
        return ActiveMembershipSerializer(memberships, many=True).data
