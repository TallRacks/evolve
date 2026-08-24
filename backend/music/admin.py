from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin

from audit.services import record_event
from core.admin import PlatformSuperuserAdminMixin

from .models import MusicCredit, Release, ReleaseLink, ReleaseTrack, Track
from .services import transition_release


@admin.register(Release)
class ReleaseAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "title",
        "primary_artist",
        "organization",
        "release_type",
        "status",
        "planned_release_date",
        "upc_ean",
        "created_at",
    )
    list_filter = (
        "organization",
        "primary_artist",
        "release_type",
        "status",
        "planned_release_date",
    )
    search_fields = ("title", "primary_artist__stage_name", "upc_ean", "catalog_number")
    autocomplete_fields = ("organization", "primary_artist", "created_by")
    readonly_fields = ("id", "status", "created_at", "updated_at")
    actions = ("schedule_selected", "release_selected", "cancel_selected", "archive_selected")
    fieldsets = (
        (
            "Identity",
            {"fields": ("id", "organization", "primary_artist", "title", "slug", "release_type")},
        ),
        (
            "Dates",
            {"fields": ("planned_release_date", "release_datetime", "original_release_date")},
        ),
        ("Identifiers", {"fields": ("upc_ean", "catalog_number")}),
        ("Business", {"fields": ("label_name", "distributor_name")}),
        ("Presentation", {"fields": ("artwork_url", "public_url", "presave_url")}),
        ("Status", {"fields": ("status",)}),
        ("Notes", {"fields": ("internal_notes",)}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change and "status" in form.changed_data:
            raise ValidationError("Use a Release lifecycle action.")
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.organization,
            action="release.updated" if change else "release.created",
            resource=obj,
            description=f"{'Updated' if change else 'Created'} release {obj.title} in admin.",
            request=request,
        )

    def _transition(self, request, queryset, status):
        for release in queryset:
            try:
                transition_release(
                    actor=request.user, release=release, to_status=status, request=request
                )
            except ValidationError as error:
                self.message_user(request, "; ".join(error.messages), messages.ERROR)

    @admin.action(description="Schedule selected releases")
    def schedule_selected(self, request, queryset):
        self._transition(request, queryset, Release.Status.SCHEDULED)

    @admin.action(description="Mark selected releases released")
    def release_selected(self, request, queryset):
        self._transition(request, queryset, Release.Status.RELEASED)

    @admin.action(description="Cancel selected releases")
    def cancel_selected(self, request, queryset):
        self._transition(request, queryset, Release.Status.CANCELLED)

    @admin.action(description="Archive selected releases")
    def archive_selected(self, request, queryset):
        self._transition(request, queryset, Release.Status.ARCHIVED)


@admin.register(Track)
class TrackAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    list_display = (
        "title",
        "version_title",
        "primary_artist",
        "organization",
        "isrc",
        "duration_seconds",
        "explicit_content",
        "status",
    )
    list_filter = ("organization", "primary_artist", "explicit_content", "status")
    search_fields = ("title", "version_title", "primary_artist__stage_name", "isrc")
    autocomplete_fields = ("organization", "primary_artist", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "id",
                    "organization",
                    "primary_artist",
                    "title",
                    "version_title",
                    "slug",
                    "status",
                )
            },
        ),
        ("Identifiers", {"fields": ("isrc", "internal_reference")}),
        ("Technical", {"fields": ("duration_seconds", "explicit_content")}),
        ("Presentation", {"fields": ("artwork_url", "audio_preview_url")}),
        ("Metadata", {"fields": ("release_year", "language", "genre", "subgenre")}),
        ("Notes", {"fields": ("internal_notes",)}),
        ("Audit metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.organization,
            action="track.updated" if change else "track.created",
            resource=obj,
            description=f"{'Updated' if change else 'Created'} track {obj.title} in admin.",
            request=request,
        )


class RelatedMusicAdmin(PlatformSuperuserAdminMixin, ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReleaseTrack)
class ReleaseTrackAdmin(RelatedMusicAdmin):
    list_display = ("release", "track", "disc_number", "track_number", "sequence", "is_focus_track")
    list_filter = ("release__organization", "is_focus_track")
    search_fields = ("release__title", "track__title")
    autocomplete_fields = ("release", "track")

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.release.organization,
            action="release.track_reordered" if change else "release.track_added",
            resource=obj.release,
            description="Updated Release tracklist in admin.",
            request=request,
        )


@admin.register(MusicCredit)
class MusicCreditAdmin(RelatedMusicAdmin):
    list_display = ("name", "credit_role", "release", "track", "organization")
    list_filter = ("organization", "credit_role")
    search_fields = ("name", "track__title", "release__title")
    autocomplete_fields = ("organization", "release", "track", "linked_artist", "linked_contact")

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        resource = obj.release or obj.track
        record_event(
            actor=request.user,
            organization=obj.organization,
            action="music.credit_updated" if change else "music.credit_added",
            resource=resource,
            description="Updated Music credit in admin.",
            request=request,
        )


@admin.register(ReleaseLink)
class ReleaseLinkAdmin(RelatedMusicAdmin):
    list_display = ("release", "platform", "url", "is_primary")
    list_filter = ("release__organization", "platform", "is_primary")
    search_fields = ("release__title", "url")
    autocomplete_fields = ("release",)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            organization=obj.release.organization,
            action="music.link_updated" if change else "music.link_added",
            resource=obj.release,
            description="Updated Release link in admin.",
            request=request,
        )
