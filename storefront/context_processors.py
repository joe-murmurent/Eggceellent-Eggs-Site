def site_roles(request):
    user = request.user
    if not user.is_authenticated:
        return {"site_is_admin": False, "site_can_see_eggs": False}

    roles = set(user.groups.values_list("name", flat=True))
    is_admin = user.is_superuser or "ADMIN" in roles
    return {"site_is_admin": is_admin, "site_can_see_eggs": is_admin or "EGGS" in roles}
