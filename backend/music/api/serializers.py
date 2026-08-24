from rest_framework import serializers

from music.models import MusicCredit, Release, ReleaseLink, ReleaseTrack, Track


class ArtistSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    stage_name = serializers.CharField()


class TrackSummarySerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="primary_artist.stage_name")
    artist_id = serializers.UUIDField(source="primary_artist_id")
    releases_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Track
        fields = (
            "id",
            "artist_id",
            "title",
            "version_title",
            "slug",
            "status",
            "artist",
            "isrc",
            "duration_seconds",
            "explicit_content",
            "artwork_url",
            "release_year",
            "genre",
            "releases_count",
        )


class TrackWriteSerializer(serializers.ModelSerializer):
    primary_artist_id = serializers.UUIDField()

    class Meta:
        model = Track
        exclude = ("organization", "primary_artist", "created_by", "created_at", "updated_at")


class CreditSerializer(serializers.ModelSerializer):
    linked_artist_id = serializers.UUIDField(required=False, allow_null=True)
    linked_contact_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = MusicCredit
        exclude = ("organization", "release", "track", "linked_artist", "linked_contact")
        read_only_fields = ("id", "created_at", "updated_at")


class ReleaseLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseLink
        exclude = ("release",)
        read_only_fields = ("id", "created_at", "updated_at")


class ReleaseTrackSerializer(serializers.ModelSerializer):
    track_id = serializers.UUIDField()
    track = TrackSummarySerializer(read_only=True)

    class Meta:
        model = ReleaseTrack
        fields = (
            "id",
            "track_id",
            "track",
            "disc_number",
            "track_number",
            "sequence",
            "is_focus_track",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ReleaseSummarySerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="primary_artist.stage_name")
    artist_id = serializers.UUIDField(source="primary_artist_id")
    track_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Release
        fields = (
            "id",
            "artist_id",
            "title",
            "slug",
            "artist",
            "release_type",
            "status",
            "planned_release_date",
            "release_datetime",
            "upc_ean",
            "artwork_url",
            "public_url",
            "presave_url",
            "track_count",
            "created_at",
        )


class ReleaseWriteSerializer(serializers.ModelSerializer):
    primary_artist_id = serializers.UUIDField()

    class Meta:
        model = Release
        exclude = ("organization", "primary_artist", "created_by", "created_at", "updated_at")
        extra_kwargs = {"status": {"read_only": True}}


class ReleaseDetailSerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="primary_artist.stage_name")
    artist_id = serializers.UUIDField(source="primary_artist_id")
    organization = serializers.SerializerMethodField()
    primary_artist = ArtistSummarySerializer()
    tracks = ReleaseTrackSerializer(source="track_placements", many=True)
    credits = CreditSerializer(many=True)
    links = ReleaseLinkSerializer(many=True)
    allowed_transitions = serializers.ListField(child=serializers.CharField())
    activity = serializers.ListField()

    class Meta:
        model = Release
        fields = "__all__"

    def get_organization(self, release):
        return {"id": release.organization_id, "name": release.organization.name}


class TrackDetailSerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="primary_artist.stage_name")
    artist_id = serializers.UUIDField(source="primary_artist_id")
    organization = serializers.SerializerMethodField()
    primary_artist = ArtistSummarySerializer()
    credits = CreditSerializer(many=True)
    releases = serializers.SerializerMethodField()
    activity = serializers.ListField()

    class Meta:
        model = Track
        fields = "__all__"

    def get_organization(self, track):
        return {"id": track.organization_id, "name": track.organization.name}

    def get_releases(self, track):
        return [
            {"id": item.release_id, "title": item.release.title, "status": item.release.status}
            for item in track.release_placements.select_related("release")
        ]


class StatusSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=Release.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class DeveloperReleaseSerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="primary_artist.stage_name")
    type = serializers.CharField(source="release_type")
    release_date = serializers.DateField(source="planned_release_date")
    upc = serializers.CharField(source="upc_ean")

    class Meta:
        model = Release
        fields = (
            "id",
            "title",
            "artist",
            "type",
            "status",
            "release_date",
            "upc",
            "artwork_url",
            "public_url",
            "presave_url",
        )


class DeveloperTrackSerializer(serializers.ModelSerializer):
    artist = serializers.CharField(source="primary_artist.stage_name")
    version = serializers.CharField(source="version_title")
    explicit = serializers.BooleanField(source="explicit_content")

    class Meta:
        model = Track
        fields = ("id", "title", "version", "artist", "isrc", "duration_seconds", "explicit")
