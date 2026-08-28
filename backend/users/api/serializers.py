from rest_framework import serializers

from organizations.models import Membership, Organization
from organizations.permissions import permissions_for_role


class ActiveMembershipSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ("id", "organization", "role", "permissions")

    def get_organization(self, membership):
        return {
            "id": membership.organization_id,
            "name": membership.organization.name,
            "slug": membership.organization.slug,
        }

    def get_permissions(self, membership):
        return permissions_for_role(membership.role)


class CurrentUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)


class SessionBootstrapSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()
    organizations = serializers.SerializerMethodField()

    def get_user(self, user):
        return CurrentUserSerializer(user).data

    def get_memberships(self, user):
        memberships = user.memberships.active().select_related("organization")
        return ActiveMembershipSerializer(memberships, many=True).data

    def get_organizations(self, user):
        if not user.is_superuser:
            return []
        return list(
            Organization.objects.filter(is_active=True)
            .order_by("name", "id")
            .values("id", "name", "slug")
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True, min_length=12)
