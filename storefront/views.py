from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import SignInForm, TripEntryForm
from .models import TripEntry, TripEntryFile

MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_TOTAL_SIZE = 50 * 1024 * 1024
MAX_FILES_PER_ENTRY = 8
INLINE_IMAGE_TYPES = {"image/avif", "image/bmp", "image/gif", "image/jpeg", "image/png", "image/webp"}


def is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name="ADMIN").exists())


def can_access_eggs(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=["ADMIN", "EGGS"]).exists()
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
    if (
        len(files) + entry.files.count() > MAX_FILES_PER_ENTRY
        or any(file.size > MAX_FILE_SIZE for file in files)
        or sum(file.size for file in files) > MAX_TOTAL_SIZE
    ):
        return "files-too-large"

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


@login_required(login_url="home")
@require_POST
def create_trip_entry(request):
    form = TripEntryForm(request.POST)
    if not form.is_valid():
        return redirect("/trip-2027/?error=invalid-entry")
    entry = form.save()
    error = _save_uploads(request, entry)
    if error:
        entry.delete()
        return redirect(f"/trip-2027/?error={error}")
    return redirect("trip_entry", pk=entry.pk)


@login_required(login_url="home")
def trip_entry(request, pk):
    entry = get_object_or_404(TripEntry.objects.prefetch_related("files"), pk=pk)
    if request.method == "POST":
        form = TripEntryForm(request.POST, instance=entry)
        if not form.is_valid():
            return render(
                request,
                "storefront/trip_entry.html",
                {"entry": entry, "form": form, "error": "invalid-entry", "is_admin": is_admin(request.user)},
                status=400,
            )
        error = _save_uploads(request, entry)
        if error:
            return redirect(f"/trip-2027/{entry.pk}/?error={error}")
        form.save()
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
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("File not found") from None
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
