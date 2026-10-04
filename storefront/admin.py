from django.contrib import admin

from .models import Organization, TripEntry, TripEntryFile


class TripEntryFileInline(admin.TabularInline):
    model = TripEntryFile
    extra = 0


@admin.register(TripEntry)
class TripEntryAdmin(admin.ModelAdmin):
    list_display = ("event_date", "event_title")
    list_filter = ("event_date",)
    search_fields = ("event_title", "event_description")
    inlines = (TripEntryFileInline,)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("business_name", "city", "state", "business_type")
    search_fields = ("business_name", "city", "registration_number")


@admin.register(TripEntryFile)
class TripEntryFileAdmin(admin.ModelAdmin):
    list_display = ("file_name", "trip_entry", "file_type")
    search_fields = ("file_name", "description")
