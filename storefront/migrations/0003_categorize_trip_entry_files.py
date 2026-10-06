from pathlib import Path, PurePosixPath

from django.core.files import File
from django.db import migrations, models
import storefront.models


IMAGE_FILE_SUFFIXES = {".avif", ".bmp", ".gif", ".heic", ".heif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
VIDEO_FILE_SUFFIXES = {".3gp", ".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm", ".wmv"}
CATEGORIES = {"images", "videos", "other"}


def _category(file_type, filename):
    suffix = PurePosixPath(filename).suffix.lower()
    normalized_type = (file_type or "").lower()
    if normalized_type.startswith("image/") or suffix in IMAGE_FILE_SUFFIXES:
        return "images"
    if normalized_type.startswith("video/") or suffix in VIDEO_FILE_SUFFIXES:
        return "videos"
    return "other"


def organize_trip_entry_files(apps, schema_editor):
    TripEntryFile = apps.get_model("storefront", "TripEntryFile")
    database_alias = schema_editor.connection.alias
    file_field = TripEntryFile._meta.get_field("file")
    storage = file_field.storage

    for category in CATEGORIES:
        Path(storage.path(f"trip_2027_files/{category}")).mkdir(parents=True, exist_ok=True)

    for stored_file in TripEntryFile.objects.using(database_alias).iterator():
        old_name = stored_file.file.name
        if not old_name or not old_name.startswith("trip_2027_files/"):
            continue
        parts = PurePosixPath(old_name).parts
        if len(parts) > 2 and parts[1] in CATEGORIES:
            continue
        if not storage.exists(old_name):
            continue

        category = _category(stored_file.file_type, old_name)
        new_name = f"trip_2027_files/{category}/{PurePosixPath(old_name).name}"
        with storage.open(old_name, "rb") as source:
            saved_name = storage.save(new_name, File(source))
        stored_file.file.name = saved_name
        stored_file.save(using=database_alias, update_fields=["file"])
        storage.delete(old_name)


class Migration(migrations.Migration):
    dependencies = [
        ("storefront", "0002_seed_roles"),
    ]

    operations = [
        migrations.RunPython(organize_trip_entry_files, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tripentryfile",
            name="file",
            field=models.FileField(upload_to=storefront.models.trip_entry_file_upload_to),
        ),
    ]