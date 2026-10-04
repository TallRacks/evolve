from django.utils import timezone
from rest_framework import serializers

from organizations.models import FeatureSetting, Invitation, Membership, Organization, RoleProfile
from users.managers import UserManager
from users.models import User
from organizations.permissions import all_permissions, permissions_for_membership


class OrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    pending_invitation_count = serializers.IntegerField(read_only=True)
    artist_count = serializers.IntegerField(read_only=True)
    active_artist_count = serializers.IntegerField(read_only=True)
    inactive_artist_count = serializers.IntegerField(read_only=True)
    promoter_count = serializers.IntegerField(read_only=True)
    venue_count = serializers.IntegerField(read_only=True)
    contact_count = serializers.IntegerField(read_only=True)
    booking_count = serializers.IntegerField(read_only=True)
    upcoming_booking_count = serializers.IntegerField(read_only=True)
    confirmed_booking_count = serializers.IntegerField(read_only=True)
    pending_booking_count = serializers.IntegerField(read_only=True)
    priority_booking_count = serializers.IntegerField(read_only=True)
    call_sheet_count = serializers.IntegerField(read_only=True)
    draft_call_sheet_count = serializers.IntegerField(read_only=True)
    published_upcoming_call_sheet_count = serializers.IntegerField(read_only=True)
    confirmed_without_call_sheet_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "is_active",
            "created_at",
            "updated_at",
            "member_count",
            "pending_invitation_count",
            "artist_count",
            "active_artist_count",
            "inactive_artist_count",
            "promoter_count",
            "venue_count",
            "contact_count",
            "booking_count",
            "upcoming_booking_count",
            "confirmed_booking_count",
            "pending_booking_count",
            "priority_booking_count",
            "call_sheet_count",
            "draft_call_sheet_count",
            "published_upcoming_call_sheet_count",
            "confirmed_without_call_sheet_count",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ("name", "slug")


class MembershipSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = (
            "id", "user", "organization", "role", "is_active",
            "permission_overrides", "role_profile", "permissions", "created_at", "updated_at",
        )

    permissions = serializers.SerializerMethodField()

    def get_permissions(self, membership):
        return permissions_for_membership(membership)

    def get_user(self, membership):
        return {
            "id": membership.user_id,
            "email": membership.user.email,
            "first_name": membership.user.first_name,
            "last_name": membership.user.last_name,
            "is_active": membership.user.is_active,
        }

    def get_organization(self, membership):
        return {
            "id": membership.organization_id,
            "name": membership.organization.name,
            "slug": membership.organization.slug,
        }




class MembershipCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(choices=Membership.Role.choices, default=Membership.Role.MEMBER)
    is_active = serializers.BooleanField(default=True)
    permission_overrides = serializers.JSONField(required=False, default=dict)
    role_profile = serializers.PrimaryKeyRelatedField(queryset=RoleProfile.objects.all(), required=False, allow_null=True)

    def validate_permission_overrides(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Permission overrides must be an object.")
        allowed = all_permissions()
        for key in ("grant", "deny"):
            values = value.get(key, [])
            if not isinstance(values, list) or any(item not in allowed for item in values):
                raise serializers.ValidationError({key: "Use only known permission names."})
        return {"grant": sorted(set(value.get("grant", []))), "deny": sorted(set(value.get("deny", [])))}

    def validate(self, attrs):
        if attrs["role"] == Membership.Role.OWNER and any((attrs.get("permission_overrides") or {}).get(key, []) for key in ("grant", "deny")):
            raise serializers.ValidationError("Owner memberships inherit all permissions and cannot use overrides.")
        if not attrs.get("is_active", True) and attrs["role"] == Membership.Role.OWNER:
            raise serializers.ValidationError("An owner membership must be active.")
        return attrs

class MembershipUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("role", "is_active", "permission_overrides", "role_profile")

    def validate_permission_overrides(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Permission overrides must be an object.")
        allowed = all_permissions()
        for key in ("grant", "deny"):
            values = value.get(key, [])
            if not isinstance(values, list) or any(item not in allowed for item in values):
                raise serializers.ValidationError({key: "Use only known permission names."})
        return {"grant": sorted(set(value.get("grant", []))), "deny": sorted(set(value.get("deny", [])))}

    def validate(self, attrs):
        role = attrs.get("role", self.instance.role if self.instance else None)
        overrides = attrs.get("permission_overrides", self.instance.permission_overrides if self.instance else {})
        if role == Membership.Role.OWNER and any((overrides or {}).get(key, []) for key in ("grant", "deny")):
            raise serializers.ValidationError("Owner memberships cannot have permission overrides.")
        return attrs


class FeatureSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureSetting
        fields = ("id", "organization", "key", "label", "description", "is_enabled", "created_at", "updated_at")
        read_only_fields = ("id", "organization", "created_at", "updated_at")


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = serializers.EmailField(source="invited_by.email", read_only=True, allow_null=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = (
            "id",
            "email",
            "role",
            "invited_by",
            "created_at",
            "expires_at",
            "accepted_at",
            "revoked_at",
            "status",
        )

    def get_status(self, invitation):
        if invitation.accepted_at:
            return "accepted"
        if invitation.revoked_at:
            return "revoked"
        if invitation.expires_at <= timezone.now():
            return "expired"
        return "pending"


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices)

    def validate_email(self, value):
        return UserManager.normalize_login_email(value)


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200, trim_whitespace=True)


class InvitationSignupSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200, trim_whitespace=True)
    full_name = serializers.CharField(max_length=300, trim_whitespace=True, min_length=2)
    password = serializers.CharField(write_only=True, min_length=12, trim_whitespace=False)


class ProfileSerializer(serializers.ModelSerializer):
    profile_image_url = serializers.CharField(required=False, allow_blank=True)
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "username",
            "profile_image_url",
            "is_superuser",
            "memberships",
        )
        read_only_fields = ("id", "email", "is_superuser", "memberships")

    def to_representation(self, user):
        data = super().to_representation(user)
        if user.profile_image_document_id:
            request = self.context.get("request")
            path = "/api/profile/image/"
            data["profile_image_url"] = request.build_absolute_uri(path) if request else path
        return data

    def get_memberships(self, user):
        return MembershipSerializer(
            user.memberships.active().select_related("user", "organization"), many=True
        ).data


class PlatformUserSerializer(serializers.ModelSerializer):
    membership_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "membership_count",
            "date_joined",
            "last_login",
        )
        read_only_fields = (
            "id",
            "email",
            "is_staff",
            "is_superuser",
            "membership_count",
            "date_joined",
            "last_login",
        )


class RoleProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleProfile
        fields = ("id", "organization", "key", "name", "description", "permissions", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_permissions(self, value):
        if not isinstance(value, list) or any(item not in all_permissions() for item in value):
            raise serializers.ValidationError("Permissions must be a list of known permission names.")
        return sorted(set(value))
