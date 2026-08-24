from django.utils import timezone
from rest_framework import serializers

from organizations.models import Invitation, Membership, Organization
from users.managers import UserManager
from users.models import User


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
            "id",
            "user",
            "organization",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        )

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


class MembershipUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ("role", "is_active")


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = serializers.EmailField(
        source="invited_by.email", read_only=True, allow_null=True
    )
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


class ProfileSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "is_superuser",
            "memberships",
        )
        read_only_fields = ("id", "email", "is_superuser", "memberships")

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
