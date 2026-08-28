"""Shared template context so the chrome is identical on every page."""

from . import mock_data, store


def _nav_items(role, profile):
    """Navigation built from data, so base.html loops instead of branching."""
    if role == mock_data.ROLE_MANAGER:
        pending = store.count_pending_logs_for_manager(profile.get("id"))
        return [
            {"label": "Team", "url_name": "dashboard:manager_team", "match": "manager_team"},
            {"label": "Programs", "url_name": "dashboard:manager_programs", "match": "manager_programs"},
            {"label": "Approvals", "url_name": "dashboard:manager_approvals",
             "match": "manager_approvals", "badge": pending},
            {"label": "FAQs", "url_name": "dashboard:faqs", "match": "faqs"},
        ]
    if role == mock_data.ROLE_DIRECTOR:
        pending = store.count_pending_programs()
        return [
            {"label": "Overview", "url_name": "dashboard:director_overview", "match": "director_overview"},
            {"label": "Programs", "url_name": "dashboard:director_programs", "match": "director_programs"},
            {"label": "Approvals", "url_name": "dashboard:director_approvals",
             "match": "director_approvals", "badge": pending},
            {"label": "FAQs", "url_name": "dashboard:faqs", "match": "faqs"},
        ]
    return [
        {"label": "Dashboard", "url_name": "dashboard:dashboard", "match": "dashboard"},
        {"label": "Log Work", "url_name": "dashboard:log_work", "match": "log_work"},
        {"label": "FAQs", "url_name": "dashboard:faqs", "match": "faqs"},
    ]


def portal(request):
    """Expose session auth state, the signed-in person, and role-aware nav."""
    signed_in = bool(request.session.get("is_authenticated"))
    role = request.session.get("role") if signed_in else None

    email = request.session.get("user_email")
    account = mock_data.DEMO_ACCOUNTS.get(email or "")
    profile = dict(account["profile"]) if account else {}

    if profile:
        profile["first_name"] = profile["name"].split()[0]
        profile["role_label"] = mock_data.ROLE_LABELS.get(role, "")
        # Session overrides let profile edits persist without a database.
        profile["phone"] = request.session.get("profile_phone", profile.get("phone", ""))
        profile["location"] = request.session.get("profile_location", profile.get("location", ""))

    return {
        "is_authenticated": signed_in,
        "role": role,
        "is_agent": role == mock_data.ROLE_AGENT,
        "is_manager": role == mock_data.ROLE_MANAGER,
        "is_director": role == mock_data.ROLE_DIRECTOR,
        "current_user": profile,
        # Existing agent templates still read current_agent.
        "current_agent": profile,
        "nav_items": _nav_items(role, profile) if signed_in else [],
    }
