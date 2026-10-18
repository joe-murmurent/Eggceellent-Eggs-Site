from pathlib import Path
from datetime import timedelta

import markdown
from django.contrib import messages
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import ItineraryCollisionForm, ItineraryStopForm, ManagedUserForm, OrganizationForm, RoleForm
from .models import ItineraryReference, ItineraryStop, Organization
from .views import is_admin

User = get_user_model()
USERS_URL = "admin_users"
ROLES_URL = "admin_roles"
ORGS_URL = "admin_organizations"
DATA_DICT_PATH = Path(__file__).resolve().parents[1] / "DataDict.md"
ITINERARY_URL = "admin_itinerary"


def _error(request, message, route):
    messages.error(request, message)
    return redirect(route)


def _success(request, message, route):
    messages.success(request, message)
    return redirect(route)


def _is_admin_group(user):
    return user.groups.filter(name="ADMIN").exists()


def _preserve_admin(user, role_names):
    if _is_admin_group(user) and "ADMIN" not in role_names:
        return User.objects.filter(groups__name="ADMIN").distinct().count() > 1
    return True


@user_passes_test(is_admin, login_url="home")
@require_http_methods(["GET", "POST"])
def admin_users(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = ManagedUserForm(request.POST)
            if form.is_valid():
                password = form.cleaned_data["password"]
                if not password:
                    form.add_error("password", "A password is required for a new account.")
                else:
                    try:
                        password_validation.validate_password(password)
                    except Exception as exc:
                        for error in getattr(exc, "error_list", [exc]):
                            form.add_error("password", error)
                    else:
                        form.save()
                        return _success(request, "User created.", USERS_URL)
            return render(request, "storefront/admin_users.html", _user_context(request, form), status=400)

        user = get_object_or_404(User, pk=request.POST.get("user_id"))
        actor = request.user
        if user.pk == actor.pk and actor.username != "joemur":
            return _error(request, "You cannot edit or delete your own user record.", USERS_URL)

        if action == "delete":
            if not _preserve_admin(user, []):
                return _error(request, "At least one user must keep the ADMIN role.", USERS_URL)
            if user.pk == actor.pk:
                return _error(request, "You cannot delete your signed-in account.", USERS_URL)
            user.delete()
            return _success(request, "User deleted.", USERS_URL)

        if action == "update":
            form = ManagedUserForm(request.POST, instance=user)
            if form.is_valid():
                role_names = list(form.cleaned_data["roles"].values_list("name", flat=True))
                if not _preserve_admin(user, role_names):
                    return _error(request, "At least one user must keep the ADMIN role.", USERS_URL)
                password = form.cleaned_data["password"]
                if password:
                    try:
                        password_validation.validate_password(password, user)
                    except Exception as exc:
                        for error in getattr(exc, "error_list", [exc]):
                            form.add_error("password", error)
                    else:
                        form.save()
                        return _success(request, "User changes saved.", USERS_URL)
                else:
                    form.save()
                    return _success(request, "User changes saved.", USERS_URL)
            return render(request, "storefront/admin_users.html", _user_context(request, form), status=400)

    return render(request, "storefront/admin_users.html", _user_context(request))


def _user_context(request, form=None):
    users = User.objects.prefetch_related("groups").order_by("username")
    return {
        "users": users,
        "roles": Group.objects.order_by("name"),
        "create_form": form or ManagedUserForm(),
        "actor": request.user,
        "active_admin_count": User.objects.filter(groups__name="ADMIN").distinct().count(),
    }


@user_passes_test(is_admin, login_url="home")
@require_http_methods(["GET", "POST"])
def admin_roles(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = RoleForm(request.POST)
            if form.is_valid():
                form.save()
                return _success(request, "Role created.", ROLES_URL)
        elif action == "update":
            role = get_object_or_404(Group, pk=request.POST.get("role_id"))
            form = RoleForm(request.POST, instance=role)
            if role.name == "ADMIN" and request.POST.get("name", "").strip().upper() != "ADMIN":
                return _error(request, "The ADMIN role cannot be renamed.", ROLES_URL)
            if form.is_valid():
                form.save()
                return _success(request, "Role changes saved.", ROLES_URL)
        elif action == "delete":
            role = get_object_or_404(Group, pk=request.POST.get("role_id"))
            if role.name == "ADMIN":
                return _error(request, "The ADMIN role cannot be deleted.", ROLES_URL)
            role.delete()
            return _success(request, "Role deleted.", ROLES_URL)
        else:
            form = RoleForm()
        messages.error(request, "Enter a valid, unique role name.")
        return render(request, "storefront/admin_roles.html", _role_context(form), status=400)

    return render(request, "storefront/admin_roles.html", _role_context())


def _role_context(form=None):
    roles = Group.objects.annotate(user_count=Count("user")).order_by("name")
    return {"roles": roles, "create_form": form or RoleForm()}


@user_passes_test(is_admin, login_url="home")
@require_http_methods(["GET", "POST"])
def admin_organizations(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = OrganizationForm(request.POST)
            if form.is_valid():
                form.save()
                return _success(request, "Organization created.", ORGS_URL)
        elif action == "update":
            organization = get_object_or_404(Organization, pk=request.POST.get("organization_id"))
            form = OrganizationForm(request.POST, instance=organization)
            if form.is_valid():
                form.save()
                return _success(request, "Organization changes saved.", ORGS_URL)
        elif action == "delete":
            get_object_or_404(Organization, pk=request.POST.get("organization_id")).delete()
            return _success(request, "Organization deleted.", ORGS_URL)
        else:
            form = OrganizationForm()
        messages.error(request, "Check the organization fields and date.")
        return render(request, "storefront/admin_organizations.html", _organization_context(form), status=400)

    return render(request, "storefront/admin_organizations.html", _organization_context())


def _organization_context(form=None):
    return {
        "organizations": Organization.objects.all(),
        "create_form": form or OrganizationForm(),
    }


@user_passes_test(is_admin, login_url="home")
@require_http_methods(["GET"])
def admin_data_dictionary(request):
    data_dictionary = DATA_DICT_PATH.read_text(encoding="utf-8")
    rendered_data_dictionary = markdown.markdown(data_dictionary, extensions=["tables"])
    return render(
        request,
        "storefront/admin_data_dictionary.html",
        {"data_dictionary_html": rendered_data_dictionary},
    )


def _shift_unbooked_after(after_date, days, exclude_pk):
    if not days:
        return
    delta = timedelta(days=days)
    later_stops = (
        ItineraryStop.objects.filter(stop_date__gt=after_date)
        .exclude(pk=exclude_pk)
        .exclude(booking_status=ItineraryStop.BOOKED)
    )
    for later in later_stops:
        later.stop_date += delta
        if later.check_in:
            later.check_in += delta
        if later.check_out:
            later.check_out += delta
        later.save(update_fields=["stop_date", "check_in", "check_out"])


def _stop_length_days(stop):
    if stop.check_in and stop.check_out and stop.check_out > stop.check_in:
        return (stop.check_out - stop.check_in).days
    return 1


@user_passes_test(is_admin, login_url="home")
@require_http_methods(["GET", "POST"])
def admin_itinerary(request):
    create_form = ItineraryStopForm()
    editing_stop = None
    edit_form = None
    collision_edit_form = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            create_form = ItineraryStopForm(request.POST)
            if create_form.is_valid():
                create_form.save()
                return _success(request, "Itinerary stop added.", ITINERARY_URL)
        elif action == "update":
            editing_stop = get_object_or_404(ItineraryStop, pk=request.POST.get("stop_id"))
            old_date = editing_stop.stop_date
            form_class = ItineraryCollisionForm if request.POST.get("form_type") == "collision" else ItineraryStopForm
            submitted_form = form_class(request.POST, instance=editing_stop)
            if form_class is ItineraryCollisionForm:
                collision_edit_form = submitted_form
            else:
                edit_form = submitted_form
            if submitted_form.is_valid():
                with transaction.atomic():
                    saved = submitted_form.save()
                    _shift_unbooked_after(old_date, (saved.stop_date - old_date).days, saved.pk)
                return _success(request, "Itinerary stop updated.", ITINERARY_URL)
        elif action == "delete":
            stop = get_object_or_404(ItineraryStop, pk=request.POST.get("stop_id"))
            with transaction.atomic():
                _shift_unbooked_after(stop.stop_date, -_stop_length_days(stop), stop.pk)
                stop.delete()
            return _success(request, "Itinerary stop deleted.", ITINERARY_URL)
        else:
            messages.error(request, "Choose a valid itinerary action.")

    stop_rows = []
    all_stops = list(ItineraryStop.objects.all())
    for stop in all_stops:
        stop_rows.append(
            {
                "stop": stop,
                "form": edit_form if stop == editing_stop and edit_form else ItineraryStopForm(instance=stop),
            }
        )

    date_counts = {}
    for stop in all_stops:
        date_counts[stop.stop_date] = date_counts.get(stop.stop_date, 0) + 1
    collision_rows = [
        {
            "stop": stop,
            "form": collision_edit_form
            if stop == editing_stop and collision_edit_form
            else ItineraryCollisionForm(instance=stop),
        }
        for stop in all_stops
        if date_counts[stop.stop_date] > 1
    ]

    map_events = []
    for stop in ItineraryStop.objects.exclude(geo_location=""):
        try:
            latitude, longitude = (float(value.strip()) for value in stop.geo_location.split(","))
        except (TypeError, ValueError):
            continue
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            map_events.append(
                {
                    "lat": latitude,
                    "lng": longitude,
                    "title": stop.destination,
                    "date": stop.stop_date.isoformat(),
                    "url": f"{reverse(ITINERARY_URL)}#stop-{stop.pk}",
                }
            )

    return render(
        request,
        "storefront/admin_itinerary.html",
        {
            "stop_rows": stop_rows,
            "collision_rows": collision_rows,
            "create_form": create_form,
            "assumptions": ItineraryReference.objects.filter(reference_type=ItineraryReference.ASSUMPTION),
            "sources": ItineraryReference.objects.filter(reference_type=ItineraryReference.SOURCE),
            "map_events": map_events,
        },
        status=400 if (not create_form.is_valid() or (edit_form and not edit_form.is_valid()) or (collision_edit_form and not collision_edit_form.is_valid())) and request.method == "POST" else 200,
    )
