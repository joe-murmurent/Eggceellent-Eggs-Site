from django.contrib import messages
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import Group
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import ManagedUserForm, OrganizationForm, RoleForm
from .models import Organization
from .views import is_admin

User = get_user_model()
USERS_URL = "admin_users"
ROLES_URL = "admin_roles"
ORGS_URL = "admin_organizations"


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
