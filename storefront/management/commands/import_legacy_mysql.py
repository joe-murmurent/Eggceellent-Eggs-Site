import os
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

import pymysql
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from storefront.models import Organization, TripEntry, TripEntryFile


class Command(BaseCommand):
    help = "Import Joe's legacy MySQL records and trip uploads into this SQLite site."

    def add_arguments(self, parser):
        parser.add_argument("--url", default=os.environ.get("LEGACY_DATABASE_URL"))
        parser.add_argument("--upload-directory", required=True)

    def handle(self, *args, **options):
        database_url = options["url"]
        if not database_url:
            raise CommandError("Pass --url or set LEGACY_DATABASE_URL for the source MySQL database.")
        parsed = urlparse(database_url)
        database_name = parsed.path.lstrip("/")
        if parsed.scheme not in {"mysql", "mysql+pymysql"} or not parsed.hostname or not database_name:
            raise CommandError("The source URL must use mysql://user:password@host:port/database.")

        try:
            connection = pymysql.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=unquote(parsed.username or ""),
                password=unquote(parsed.password or ""),
                database=database_name,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10,
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users ORDER BY id")
                users = cursor.fetchall()
                cursor.execute("SELECT roles.name, user_roles.user_id FROM user_roles JOIN roles ON roles.id = user_roles.role_id")
                user_roles = cursor.fetchall()
                cursor.execute("SELECT * FROM roles ORDER BY id")
                roles = cursor.fetchall()
                cursor.execute("SELECT * FROM organization ORDER BY id")
                organizations = cursor.fetchall()
                cursor.execute("SELECT * FROM trip_entry ORDER BY id")
                entries = cursor.fetchall()
                cursor.execute("SELECT * FROM trip_entry_file ORDER BY id")
                files = cursor.fetchall()
        except pymysql.MySQLError as exc:
            raise CommandError(f"Could not read the source database: {exc.__class__.__name__}.") from exc
        finally:
            if "connection" in locals():
                connection.close()

        source_uploads = Path(options["upload_directory"]).resolve()
        destination_uploads = (Path(settings.MEDIA_ROOT) / "trip_2027_files").resolve()
        file_map = {}
        for record in files:
            location = record["file_location"].replace("\\", "/")
            stored_name = PurePosixPath(location).name
            if location != f"trip_2027_files/{stored_name}" or not re.fullmatch(
                r"[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}", stored_name, re.I
            ):
                raise CommandError(f"Refusing unexpected legacy file path for record {record['id']}.")
            source_path = source_uploads / stored_name
            if not source_path.is_file():
                raise CommandError(f"Legacy upload is missing for file record {record['id']}.")
            file_map[record["id"]] = (source_path, f"trip_2027_files/{stored_name}")

        role_names = {role["name"].strip().upper() for role in roles}
        role_names.update(name.strip().upper() for name in (row["name"] for row in roles))
        User = get_user_model()
        roles_by_user = {}
        for assignment in user_roles:
            roles_by_user.setdefault(assignment["user_id"], set()).add(assignment["name"].strip().upper())

        with transaction.atomic():
            groups = {name: Group.objects.get_or_create(name=name)[0] for name in role_names}
            for record in users:
                legacy_digest = str(record["password"]).lower()
                if not re.fullmatch(r"[\da-f]{64}", legacy_digest):
                    raise CommandError(f"User {record['username']} has an unsupported legacy password hash.")
                user, _ = User.objects.update_or_create(
                    pk=record["id"],
                    defaults={
                        "username": record["username"],
                        "first_name": record.get("firstname", ""),
                        "last_name": record.get("lastname", ""),
                        "password": f"legacy_sha256${legacy_digest}",
                        "is_staff": False,
                        "is_superuser": False,
                        "is_active": True,
                    },
                )
                user.groups.set([groups[name] for name in roles_by_user.get(user.pk, set()) if name in groups])

            for record in organizations:
                Organization.objects.update_or_create(
                    pk=record["id"],
                    defaults={
                        "business_name": record.get("business_name"),
                        "street_address": record.get("street_address"),
                        "city": record.get("city"),
                        "state": record.get("state"),
                        "postal_code": record.get("postal_code"),
                        "business_type": record.get("business_type"),
                        "business_start_date": record.get("business_start_date"),
                        "license": record.get("license"),
                        "registration_number": record.get("registration_number"),
                    },
                )

            for record in entries:
                TripEntry.objects.update_or_create(
                    pk=record["id"],
                    defaults={
                        "event_date": record["event_date"],
                        "event_title": record["event_title"],
                        "event_description": record.get("event_description"),
                    },
                )

            for record in files:
                if record["trip_entry_id"] not in {entry["id"] for entry in entries}:
                    raise CommandError(f"Trip file {record['id']} has no matching event.")
                _, stored_name = file_map[record["id"]]
                TripEntryFile.objects.update_or_create(
                    pk=record["id"],
                    defaults={
                        "trip_entry_id": record["trip_entry_id"],
                        "file": stored_name,
                        "file_name": record["file_name"],
                        "file_type": record["file_type"],
                        "description": record.get("description"),
                    },
                )

        destination_uploads.mkdir(parents=True, exist_ok=True)
        for source_path, stored_name in file_map.values():
            destination_path = destination_uploads / Path(stored_name).name
            if not destination_path.exists():
                shutil.copy2(source_path, destination_path)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(users)} users, {len(roles)} roles, {len(organizations)} organizations, "
                f"{len(entries)} trip entries, and {len(files)} files into SQLite."
            )
        )
