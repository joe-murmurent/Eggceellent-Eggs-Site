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

    class Meta:
        ordering = ["-event_date", "-id"]
        verbose_name = "trip entry"
        verbose_name_plural = "trip entries"

    def __str__(self):
        return f"{self.event_date}: {self.event_title}"


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
