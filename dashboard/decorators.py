"""Session-only access control. No Django auth app, no user model."""

from functools import wraps
from urllib.parse import quote, urlparse

from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse

from . import mock_data

# Which roles may reach each named route. Routes absent from this map are
# public. Kept here rather than in mock_data because it is app wiring, not
# reference data.
ROUTE_ROLES = {
    "dashboard": {mock_data.ROLE_AGENT},
    "log_work": {mock_data.ROLE_AGENT},
    "manager_team": {mock_data.ROLE_MANAGER},
    "manager_programs": {mock_data.ROLE_MANAGER},
    "manager_approvals": {mock_data.ROLE_MANAGER},
    "director_overview": {mock_data.ROLE_DIRECTOR},
    "director_programs": {mock_data.ROLE_DIRECTOR},
    "director_approvals": {mock_data.ROLE_DIRECTOR},
}


def role_home_url(role):
    """Where a given role lands after sign in."""
    return reverse(mock_data.ROLE_HOME.get(role, "dashboard:landing"))


def path_allowed(path, role):
    """True when `path` is an in-site route this role may open."""
    if not path or not path.startswith("/") or path.startswith("//"):
        return False
    try:
        match = resolve(urlparse(path).path)
    except Resolver404:
        return False
    allowed = ROUTE_ROLES.get(match.url_name)
    return allowed is None or role in allowed


def role_required(*roles):
    """Restrict a view to the given roles.

    Signed out  -> /login/?next=<path>
    Wrong role  -> a styled 403 page with the portal chrome, never a bare 403.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.session.get("is_authenticated"):
                login_url = reverse("dashboard:login")
                return redirect(f"{login_url}?next={quote(request.get_full_path())}")

            role = request.session.get("role")
            if roles and role not in roles:
                return render(
                    request,
                    "dashboard/403.html",
                    {"home_url": role_home_url(role)},
                    status=403,
                )
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


# Existing agent-only views keep working unchanged.
agent_required = role_required(mock_data.ROLE_AGENT)
