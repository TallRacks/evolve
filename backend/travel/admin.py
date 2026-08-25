from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    AccommodationRoomAssignment,
    AccommodationStay,
    ItineraryTraveller,
    TravelItinerary,
    TravelSegment,
    TravelSegmentTraveller,
)


class SafeAdmin(ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TravelItinerary)
class TravelItineraryAdmin(SafeAdmin):
    list_display = ("title", "organization", "artist", "booking", "status", "starts_at", "ends_at")
    list_filter = ("organization", "status", "artist")
    search_fields = ("title", "artist__stage_name", "booking__reference")
    readonly_fields = ("status", "archived_at", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("organization", "title")}),
        ("Artist / Booking", {"fields": ("artist", "booking")}),
        ("Timing", {"fields": ("starts_at", "ends_at", "timezone")}),
        ("Status", {"fields": ("status", "archived_at")}),
        ("Notes", {"fields": ("purpose", "notes")}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )


@admin.register(ItineraryTraveller)
class TravellerAdmin(SafeAdmin):
    list_display = ("display_name", "itinerary", "traveller_type", "is_active")
    list_filter = ("traveller_type", "is_active", "itinerary__organization")
    search_fields = ("display_name", "itinerary__title", "artist__stage_name")


@admin.register(TravelSegment)
class SegmentAdmin(SafeAdmin):
    list_display = (
        "itinerary",
        "segment_type",
        "provider",
        "service_number",
        "departure_at",
        "arrival_at",
        "status",
    )
    list_filter = ("itinerary__organization", "segment_type", "status")
    search_fields = (
        "itinerary__title",
        "itinerary__artist__stage_name",
        "provider",
        "service_number",
        "departure_location",
        "arrival_location",
    )
    readonly_fields = ("status", "created_at", "updated_at")


@admin.register(AccommodationStay)
class StayAdmin(SafeAdmin):
    list_display = ("itinerary", "property_name", "city", "check_in_at", "check_out_at", "status")
    list_filter = ("itinerary__organization", "status", "country")
    search_fields = ("itinerary__title", "property_name", "city")
    readonly_fields = ("status", "created_at", "updated_at")


admin.site.register(TravelSegmentTraveller, SafeAdmin)
admin.site.register(AccommodationRoomAssignment, SafeAdmin)
