"""Shared template context so the navbar is identical on every page."""

from . import mock_data


def portal(request):
    """Expose session auth state and the agent behind the profile menu."""
    signed_in = bool(request.session.get("is_authenticated"))
    agent = dict(
        mock_data.PROFILE_DATA,
        first_name=mock_data.PROFILE_DATA["name"].split()[0],
        # Session overrides let profile edits persist without a database.
        phone=request.session.get("profile_phone", mock_data.PROFILE_DATA["phone"]),
        location=request.session.get("profile_location", mock_data.PROFILE_DATA["location"]),
    )
    return {"is_authenticated": signed_in, "current_agent": agent}
