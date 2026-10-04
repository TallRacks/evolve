from rest_framework import serializers

from artists.models import Artist, ArtistPortalLink, ArtistTeamAssignment, ArtistToolkit


class ArtistSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    team_count = serializers.IntegerField(read_only=True)
    portal_user_count = serializers.IntegerField(read_only=True)
    primary_manager = serializers.SerializerMethodField()

    class Meta:
        model = Artist
        fields = (
            "id",
            "organization",
            "stage_name",
            "legal_name",
            "slug",
            "status",
            "email",
            "phone",
            "biography",
            "website",
            "country",
            "city",
            "management_email",
            "booking_email",
            "profile_image_url",
            "team_count",
            "portal_user_count",
            "primary_manager",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "team_count",
            "portal_user_count",
            "primary_manager",
            "created_at",
            "updated_at",
        )

    def get_organization(self, artist):
        return {"id": artist.organization_id, "name": artist.organization.name}

    def get_primary_manager(self, artist):
        assignments = getattr(artist, "prefetched_team", None)
        if assignments is None:
            assignment = (
                artist.team_assignments.filter(is_active=True, is_primary=True)
                .select_related("membership__user")
                .first()
            )
        else:
            assignment = next(
                (item for item in assignments if item.is_primary and item.is_active),
                None,
            )
        if not assignment:
            return None
        user = assignment.membership.user
        return {
            "id": assignment.id,
            "name": f"{user.first_name} {user.last_name}".strip() or user.email,
            "email": user.email,
        }


class ArtistWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = (
            "stage_name",
            "legal_name",
            "slug",
            "status",
            "email",
            "phone",
            "biography",
            "website",
            "country",
            "city",
            "management_email",
            "booking_email",
            "profile_image_url",
        )


class ArtistToolkitSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArtistToolkit
        exclude = ("artist",)
        read_only_fields = ("id", "created_at", "updated_at")


class TeamAssignmentSerializer(serializers.ModelSerializer):
    member = serializers.SerializerMethodField()

    class Meta:
        model = ArtistTeamAssignment
        fields = (
            "id",
            "member",
            "responsibility",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "member", "created_at", "updated_at")

    def get_member(self, assignment):
        membership = assignment.membership
        user = membership.user
        return {
            "membership_id": membership.id,
            "user_id": user.id,
            "email": user.email,
            "name": f"{user.first_name} {user.last_name}".strip() or user.email,
            "organization_role": membership.role,
            "membership_active": membership.is_active,
        }


class TeamAssignmentCreateSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField()
    responsibility = serializers.ChoiceField(
        choices=ArtistTeamAssignment.Responsibility.choices
    )
    is_primary = serializers.BooleanField(default=False)


class PortalLinkSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = ArtistPortalLink
        fields = ("id", "user", "relationship", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def get_user(self, link):
        return {
            "id": link.user_id,
            "email": link.user.email,
            "name": f"{link.user.first_name} {link.user.last_name}".strip()
            or link.user.email,
        }


class PortalLinkCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    relationship = serializers.ChoiceField(
        choices=ArtistPortalLink.Relationship.choices
    )


def display_name(user):
    return f"{user.first_name} {user.last_name}".strip() or user.email


class PortalArtistSerializer(serializers.ModelSerializer):
    organization = serializers.CharField(source="organization.name")
    team = serializers.SerializerMethodField()

    class Meta:
        model = Artist
        fields = (
            "id",
            "organization",
            "stage_name",
            "status",
            "profile_image_url",
            "biography",
            "website",
            "city",
            "country",
            "management_email",
            "booking_email",
            "team",
        )

    def get_team(self, artist):
        assignments = artist.team_assignments.filter(is_active=True).select_related(
            "membership__user"
        )
        return [
            {
                "name": display_name(item.membership.user),
                "email": item.membership.user.email,
                "responsibility": item.responsibility,
                "is_primary": item.is_primary,
            }
            for item in assignments
        ]


class DeveloperArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = (
            "id",
            "stage_name",
            "slug",
            "status",
            "city",
            "country",
            "website",
            "profile_image_url",
            "updated_at",
        )
