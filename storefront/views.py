import json
from pathlib import Path, PurePosixPath
import re
import time
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import SuspiciousFileOperation
from django.core.files import File
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import SignInForm, TripEntryForm
from .models import VIDEO_FILE_SUFFIXES, TripEntry, TripEntryFile

MAX_FILES_PER_ENTRY = 8
UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024
INLINE_IMAGE_TYPES = {"image/avif", "image/bmp", "image/gif", "image/jpeg", "image/png", "image/webp"}


class LimitedFile:
    def __init__(self, file_object, length):
        self.file_object = file_object
        self.remaining = length

    def read(self, size=-1):
        if self.remaining <= 0:
            return b""
        if size < 0 or size > self.remaining:
            size = self.remaining
        content = self.file_object.read(size)
        self.remaining -= len(content)
        return content

    def close(self):
        self.file_object.close()


def _parse_byte_range(range_header, file_size):
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip(), re.IGNORECASE)
    if not match:
        return None

    start_text, end_text = match.groups()
    if not start_text and not end_text:
        return None
    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
            if start >= file_size or end < start:
                raise ValueError
            return start, min(end, file_size - 1)

        suffix_length = int(end_text)
        if suffix_length <= 0 or file_size == 0:
            raise ValueError
        return max(file_size - suffix_length, 0), file_size - 1
    except ValueError:
        raise ValueError("Unsatisfiable byte range") from None


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name="ADMIN").exists())


def can_access_eggs(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=["ADMIN", "EGGS"]).exists()
    )


def _is_unsupported_video(file_name, file_type):
    suffix = PurePosixPath(file_name.replace("\\", "/")).suffix.lower()
    content_type = (file_type or "").lower()
    return (suffix in VIDEO_FILE_SUFFIXES and suffix != ".mp4") or (
        content_type.startswith("video/") and content_type != "video/mp4"
    )


def home(request):
    form = SignInForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["username"].strip(),
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            return redirect("home")
        form.add_error(None, "The username or password is incorrect.")

    return render(
        request,
        "storefront/home.html",
        {
            "form": form,
            "entry_count": TripEntry.objects.count() if request.user.is_authenticated else 0,
            "latest_entry": TripEntry.objects.first() if request.user.is_authenticated else None,
        },
    )


@require_POST
def log_out(request):
    logout(request)
    return redirect("home")


@login_required(login_url="home")
@require_POST
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed.")
    else:
        messages.error(request, "Check the current password and new password fields.")
    return redirect("home")


@login_required(login_url="home")
def trip_index(request):
    entries = TripEntry.objects.all().prefetch_related("files")
    return render(
        request,
        "storefront/trip_index.html",
        {
            "entries": entries,
            "is_admin": is_admin(request.user),
            "error": request.GET.get("error"),
            "create_form": TripEntryForm(),
        },
    )


def _save_uploads(request, entry):
    files = [file for file in request.FILES.getlist("files") if file.size]
    descriptions = request.POST.getlist("file_descriptions")
    if any(len(description) > 65535 for description in descriptions):
        return "file-description-invalid"
    if any(_is_unsupported_video(uploaded.name, uploaded.content_type) for uploaded in files):
        return "video-format-not-allowed"
    if len(files) + entry.files.count() > MAX_FILES_PER_ENTRY:
        return "too-many-files"

    created_files = []
    try:
        for index, uploaded in enumerate(files):
            description = descriptions[index].strip() if index < len(descriptions) else ""
            file_type = (uploaded.content_type or "application/octet-stream").lower()
            created = TripEntryFile.objects.create(
                trip_entry=entry,
                file=uploaded,
                file_name=uploaded.name.replace("\\", "/").rsplit("/", 1)[-1][:255] or "upload",
                file_type=file_type,
                description=description or None,
            )
            created_files.append(created)
    except (OSError, SuspiciousFileOperation):
        for created in created_files:
            created.file.delete(save=False)
            created.delete()
        return "invalid-upload"
    return None


def _upload_metadata(request):
    try:
        upload_id = uuid.UUID(request.POST.get("upload_id", ""))
        offset = int(request.POST.get("offset", ""))
        total_size = int(request.POST.get("total_size", ""))
    except (TypeError, ValueError):
        return None

    chunk = request.FILES.get("chunk")
    file_name = request.POST.get("file_name", "").replace("\\", "/").rsplit("/", 1)[-1][:255]
    file_type = (request.POST.get("file_type") or "application/octet-stream").lower()[:255]
    description = request.POST.get("description", "")
    if _is_unsupported_video(file_name, file_type):
        return {"error": "video-format-not-allowed"}
    if (
        chunk is None
        or not file_name
        or total_size <= 0
        or offset < 0
        or chunk.size <= 0
        or chunk.size > UPLOAD_CHUNK_SIZE
        or offset + chunk.size > total_size
        or len(description) > 65535
    ):
        return None

    return {
        "upload_id": upload_id,
        "offset": offset,
        "total_size": total_size,
        "file_name": file_name,
        "file_type": file_type,
        "description": description.strip(),
        "chunk": chunk,
    }


@login_required(login_url="home")
@require_POST
def upload_trip_file(request, pk):
    entry = get_object_or_404(TripEntry, pk=pk)
    upload = _upload_metadata(request)
    if isinstance(upload, dict) and "error" in upload:
        return JsonResponse(upload, status=415)
    if upload is None:
        return JsonResponse({"error": "invalid-chunk"}, status=400)

    upload_dir = Path(settings.MEDIA_ROOT) / ".upload_chunks" / str(request.user.pk)
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return JsonResponse({"error": "upload-storage-unavailable"}, status=500)
    for stale_path in upload_dir.iterdir():
        try:
            if stale_path.is_file() and time.time() - stale_path.stat().st_mtime > 24 * 60 * 60:
                stale_path.unlink()
        except OSError:
            continue
    stem = str(upload["upload_id"])
    chunk_path = upload_dir / f"{stem}.part"
    metadata_path = upload_dir / f"{stem}.json"
    metadata = {
        "entry_id": entry.pk,
        "total_size": upload["total_size"],
        "file_name": upload["file_name"],
        "file_type": upload["file_type"],
        "description": upload["description"],
    }

    if metadata_path.exists():
        try:
            saved_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return JsonResponse({"error": "invalid-upload-state"}, status=400)
        if saved_metadata != metadata:
            return JsonResponse({"error": "upload-metadata-mismatch"}, status=400)
    elif upload["offset"] == 0:
        if entry.files.count() >= MAX_FILES_PER_ENTRY:
            return JsonResponse({"error": "too-many-files"}, status=400)
        try:
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        except OSError:
            return JsonResponse({"error": "upload-storage-unavailable"}, status=500)
    else:
        return JsonResponse({"error": "upload-state-missing"}, status=409)

    expected_offset = chunk_path.stat().st_size if chunk_path.exists() else 0
    if upload["offset"] != expected_offset:
        return JsonResponse({"error": "chunk-offset-mismatch", "expected_offset": expected_offset}, status=409)

    try:
        with chunk_path.open("ab") as destination:
            for content in upload["chunk"].chunks():
                destination.write(content)
    except OSError:
        return JsonResponse({"error": "upload-storage-unavailable"}, status=500)

    next_offset = chunk_path.stat().st_size
    if next_offset < upload["total_size"]:
        return JsonResponse({"complete": False, "next_offset": next_offset})

    if entry.files.count() >= MAX_FILES_PER_ENTRY:
        chunk_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        return JsonResponse({"error": "too-many-files"}, status=400)

    created = TripEntryFile(
        trip_entry=entry,
        file_name=upload["file_name"],
        file_type=upload["file_type"],
        description=upload["description"] or None,
    )
    try:
        with chunk_path.open("rb") as source:
            created.file.save(upload["file_name"], File(source), save=True)
    except (OSError, SuspiciousFileOperation):
        if created.file:
            created.file.delete(save=False)
        return JsonResponse({"error": "upload-storage-unavailable"}, status=500)
    finally:
        chunk_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

    return JsonResponse({"complete": True, "file_name": created.file_name})


@login_required(login_url="home")
@require_POST
def create_trip_entry(request):
    form = TripEntryForm(request.POST)
    if not form.is_valid():
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": "invalid-entry"}, status=400)
        return redirect("/trip-2027/?error=invalid-entry")
    entry = form.save()
    error = _save_uploads(request, entry)
    if error:
        entry.delete()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": error}, status=400)
        return redirect(f"/trip-2027/?error={error}")
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "entry_url": reverse("trip_entry", args=[entry.pk]),
                "upload_url": reverse("upload_trip_file", args=[entry.pk]),
            }
        )
    return redirect("trip_entry", pk=entry.pk)


@login_required(login_url="home")
def trip_entry(request, pk):
    entry = get_object_or_404(TripEntry.objects.prefetch_related("files"), pk=pk)
    if request.method == "POST":
        form = TripEntryForm(request.POST, instance=entry)
        if not form.is_valid():
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": "invalid-entry"}, status=400)
            return render(
                request,
                "storefront/trip_entry.html",
                {"entry": entry, "form": form, "error": "invalid-entry", "is_admin": is_admin(request.user)},
                status=400,
            )
        error = _save_uploads(request, entry)
        if error:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": error}, status=400)
            return redirect(f"/trip-2027/{entry.pk}/?error={error}")
        form.save()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "entry_url": reverse("trip_entry", args=[entry.pk]),
                    "upload_url": reverse("upload_trip_file", args=[entry.pk]),
                }
            )
        return redirect("trip_entry", pk=entry.pk)

    return render(
        request,
        "storefront/trip_entry.html",
        {
            "entry": entry,
            "form": TripEntryForm(instance=entry),
            "error": request.GET.get("error"),
            "is_admin": is_admin(request.user),
        },
    )


@login_required(login_url="home")
@require_POST
def update_file_description(request, pk, file_pk):
    entry = get_object_or_404(TripEntry, pk=pk)
    trip_file = get_object_or_404(TripEntryFile, pk=file_pk, trip_entry=entry)
    description = request.POST.get("description", "").strip()
    if len(description) > 65535:
        return redirect(f"/trip-2027/{entry.pk}/?error=file-description-invalid")
    trip_file.description = description or None
    trip_file.save(update_fields=["description"])
    return redirect("trip_entry", pk=entry.pk)


@login_required(login_url="home")
@require_POST
def delete_trip_file(request, pk, file_pk):
    entry = get_object_or_404(TripEntry, pk=pk)
    trip_file = get_object_or_404(TripEntryFile, pk=file_pk, trip_entry=entry)
    trip_file.file.delete(save=False)
    trip_file.delete()
    return redirect("trip_entry", pk=entry.pk)


@login_required(login_url="home")
@user_passes_test(is_admin, login_url="home")
@require_POST
def delete_trip_entry(request, pk):
    entry = get_object_or_404(TripEntry, pk=pk)
    for trip_file in entry.files.all():
        trip_file.file.delete(save=False)
    entry.delete()
    return redirect("trip_index")


@login_required(login_url="home")
def download_trip_file(request, pk):
    trip_file = get_object_or_404(TripEntryFile.objects.select_related("trip_entry"), pk=pk)
    try:
        trip_file.file.open("rb")
        if trip_file.is_mp4_video:
            file_size = trip_file.file.size
        else:
            file_size = None
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("File not found") from None

    if trip_file.is_mp4_video:
        content_type = "video/mp4"
        range_header = request.headers.get("Range")
        try:
            byte_range = _parse_byte_range(range_header, file_size) if range_header else None
        except ValueError:
            trip_file.file.close()
            response = HttpResponse(status=416, content_type=content_type)
            response["Content-Range"] = f"bytes */{file_size}"
        else:
            if byte_range:
                start, end = byte_range
                trip_file.file.seek(start)
                response = FileResponse(
                    LimitedFile(trip_file.file, end - start + 1),
                    content_type=content_type,
                    as_attachment=False,
                    filename=trip_file.file_name,
                )
                response.status_code = 206
                response["Content-Length"] = str(end - start + 1)
                response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            else:
                response = FileResponse(
                    trip_file.file,
                    content_type=content_type,
                    as_attachment=False,
                    filename=trip_file.file_name,
                )
        response["Accept-Ranges"] = "bytes"
    else:
        content_type = trip_file.file_type if trip_file.file_type in INLINE_IMAGE_TYPES else "application/octet-stream"
        response = FileResponse(
            trip_file.file,
            content_type=content_type,
            as_attachment=content_type == "application/octet-stream",
            filename=trip_file.file_name,
        )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required(login_url="home")
@user_passes_test(can_access_eggs, login_url="home")
def eggs(request):
    return render(request, "storefront/eggs.html")
