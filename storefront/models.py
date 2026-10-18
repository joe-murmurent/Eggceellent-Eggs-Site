from django.conf import settings
from django.db import models
from pathlib import PurePosixPath


IMAGE_FILE_SUFFIXES = {".avif", ".bmp", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
VIDEO_FILE_SUFFIXES = {".3gp", ".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm", ".wmv"}


def trip_entry_file_upload_to(instance, filename):
    safe_name = PurePosixPath(filename.replace("\\", "/")).name
    suffix = PurePosixPath(safe_name).suffix.lower()
    file_type = (instance.file_type or "").lower()
    if file_type.startswith("image/") or suffix in IMAGE_FILE_SUFFIXES:
        category = "images"
    elif file_type.startswith("video/") or suffix in VIDEO_FILE_SUFFIXES:
        category = "videos"
    else:
        category = "other"
    return f"trip_2027_files/{category}/{safe_name}"


class Organization(models.Model):
    business_name = models.TextField(blank=True, null=True)
    street_address = models.TextField(blank=True, null=True)
    city = models.TextField(blank=True, null=True)
    state = models.TextField(blank=True, null=True)
    postal_code = models.TextField(blank=True, null=True)
    business_type = models.TextField(blank=True, null=True)
    business_start_date = models.DateField(blank=True, null=True)
    license = models.TextField(blank=True, null=True)
    registration_number = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["id"]
        verbose_name_plural = "organizations"

    def __str__(self):
        return self.business_name or f"Organization {self.pk}"


class TripEntry(models.Model):
    event_date = models.DateField()
    event_title = models.TextField()
    event_description = models.TextField(blank=True, null=True)
    geo_location = models.CharField(max_length=64, blank=True, default="", verbose_name="geo-location")

    class Meta:
        ordering = ["-event_date", "-id"]
        verbose_name = "trip entry"
        verbose_name_plural = "trip entries"

    def __str__(self):
        return f"{self.event_date}: {self.event_title}"


class ItineraryStop(models.Model):
    BOOK = "Book"
    BOOKED = "Booked"
    BOOKING_STATUSES = [(BOOK, "Book"), (BOOKED, "Booked")]

    day_number = models.PositiveSmallIntegerField()
    stop_date = models.DateField()
    destination = models.CharField(max_length=180)
    preferred_campground = models.CharField(max_length=200, blank=True)
    alternate_campground = models.CharField(max_length=200, blank=True)
    check_in = models.DateField(blank=True, null=True)
    check_out = models.DateField(blank=True, null=True)
    route = models.CharField(max_length=255, blank=True)
    drive_time = models.CharField(max_length=80, blank=True)
    site_type = models.CharField(max_length=100, blank=True)
    booking_requirements = models.TextField(blank=True)
    price_or_membership = models.CharField(max_length=100, blank=True)
    booking_opening_estimate = models.CharField(max_length=80, blank=True)
    attractions = models.TextField(blank=True)
    landscape = models.CharField(max_length=100, blank=True)
    fuel_errands = models.TextField(blank=True)
    stop_category = models.CharField(max_length=100, blank=True)
    weather = models.TextField(blank=True)
    towing_notes = models.TextField(blank=True)
    booking_status = models.CharField(max_length=40, choices=BOOKING_STATUSES, default=BOOK)
    booking_confirmation = models.CharField(max_length=100, blank=True)
    geo_location = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["stop_date", "day_number", "id"]
        verbose_name = "itinerary stop"
        verbose_name_plural = "itinerary stops"

    def __str__(self):
        return f"Day {self.day_number}: {self.destination}"


class ItineraryReference(models.Model):
    ASSUMPTION = "assumption"
    SOURCE = "source"
    REFERENCE_TYPES = [(ASSUMPTION, "Planning assumption"), (SOURCE, "Source")]

    reference_type = models.CharField(max_length=20, choices=REFERENCE_TYPES)
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True)
    url = models.URLField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["reference_type", "display_order", "id"]
        verbose_name = "itinerary reference"
        verbose_name_plural = "itinerary references"

    def __str__(self):
        return self.title


class TripEntryFile(models.Model):
    trip_entry = models.ForeignKey(
        TripEntry,
        on_delete=models.CASCADE,
        related_name="files",
    )
    file = models.FileField(upload_to=trip_entry_file_upload_to)
    file_name = models.TextField()
    file_type = models.TextField()
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "trip entry file"
        verbose_name_plural = "trip entry files"

    def __str__(self):
        return self.file_name

    @property
    def is_mp4_video(self):
        return self.file_name.lower().endswith(".mp4") or self.file_type.lower() == "video/mp4"
