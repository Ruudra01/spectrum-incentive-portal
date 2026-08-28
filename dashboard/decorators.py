"""Session-only access control. No Django auth app, no user model."""

from functools import wraps
from urllib.parse import quote

from django.shortcuts import redirect
from django.urls import reverse


def agent_required(view):
    """Send signed-out visitors to /login/?next=<current path>."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.session.get("is_authenticated"):
            return redirect(f"{reverse('dashboard:login')}?next={quote(request.get_full_path())}")
        return view(request, *args, **kwargs)

    return wrapper
