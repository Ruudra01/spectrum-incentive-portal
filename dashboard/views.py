import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import chat_responses, mock_data, store
from .decorators import agent_required, path_allowed, role_required, role_home_url


def _progress(points):
    """Tier progress for a point total, or None once the top tier is reached."""
    result = mock_data.points_to_next_tier(points)
    if result is None:
        return None
    name, needed, percent = result
    return {"name": name, "needed": needed, "percent": percent}


def _sparkline(values, width=260, height=64, pad=8):
    """Plot points for an inline SVG polyline. Flat series get a mid-height line."""
    low, high = min(values), max(values)
    span = (high - low) or 1
    step = (width - 2 * pad) / (len(values) - 1)
    plot = height - 2 * pad
    return [
        {
            "week": index + 1,
            "value": value,
            "x": round(pad + index * step, 1),
            "y": round(height - pad - (value - low) / span * plot, 1),
        }
        for index, value in enumerate(values)
    ]


def landing(request):
    """Marketing landing page. All figures come from mock_data."""
    agent = mock_data.CURRENT_AGENT
    return render(
        request,
        "dashboard/landing.html",
        {
            "tiers": mock_data.TIERS,
            "agent": agent,
            "agent_tier": mock_data.get_tier(agent["points"]),
            "next_tier": _progress(agent["points"]),
            "leaderboard": mock_data.LEADERBOARD,
            "kpi_stats": mock_data.KPI_STATS,
            "weekly_points": mock_data.WEEKLY_POINTS,
            "headline_stat": mock_data.HEADLINE_STAT,
        },
    )


@agent_required
def agent_dashboard(request):
    """Field agent dashboard. Every number originates in mock_data."""
    agent = mock_data.CURRENT_AGENT

    # Tier and next-tier progress are precomputed per row so the expandable
    # detail panels ship server-rendered and the JS only toggles them.
    rows = [
        dict(
            entry,
            tier=mock_data.get_tier(entry["points"]),
            next_tier=_progress(entry["points"]),
            is_current=entry["id"] == agent["id"],
        )
        for entry in mock_data.LEADERBOARD
    ]

    return render(
        request,
        "dashboard/dashboard.html",
        {
            "agent": agent,
            "first_name": agent["name"].split()[0],
            "agent_tier": mock_data.get_tier(agent["points"]),
            "next_tier": _progress(agent["points"]),
            "rows": rows,
            "regions": sorted({entry["region"] for entry in mock_data.LEADERBOARD}),
            # decimals is presentation only, so it is derived here rather
            # than stored alongside the figures in mock_data.
            "kpi_stats": [
                dict(kpi, decimals=0 if float(kpi["value"]).is_integer() else 1)
                for kpi in mock_data.KPI_STATS
            ],
            "weekly_points": mock_data.WEEKLY_POINTS,
            "sparkline": _sparkline(mock_data.WEEKLY_POINTS),
            "faq": chat_responses.FAQ_RESPONSES,
        },
    )


@require_POST
def chat_api(request):
    """Demo policy assistant. Matches canned answers; no model is called."""
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Malformed JSON body."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Expected a JSON object."}, status=400)

    message = (payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "A message is required."}, status=400)

    return JsonResponse({"reply": chat_responses.match_question(message)})


def faqs(request):
    """FAQ page. Content is the same FAQ_RESPONSES the chatbot answers from,
    so the page and the assistant can never disagree."""
    return render(request, "dashboard/faqs.html", {"faq": chat_responses.FAQ_RESPONSES})


def _safe_next(raw):
    """Only allow a relative in-site path — never an external redirect."""
    if raw and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return None


def login(request):
    """Session-only sign in against DEMO_ACCOUNTS. No auth app, no user model."""
    if request.session.get("is_authenticated"):
        return redirect(role_home_url(request.session.get("role")))

    error = None
    email = ""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        account = mock_data.DEMO_ACCOUNTS.get(email.lower())

        if account and password == account["password"]:
            role = account["role"]
            request.session["is_authenticated"] = True
            request.session["user_email"] = account["profile"]["email"]
            request.session["role"] = role
            request.session["display_name"] = account["profile"]["name"]

            # Honour ?next= only when it is in-site AND open to this role.
            requested = request.POST.get("next")
            target = requested if path_allowed(requested, role) else role_home_url(role)
            return redirect(target)

        # Deliberately non-specific: never reveal which field was wrong.
        error = "The email or password you entered is incorrect."

    return render(
        request,
        "dashboard/login.html",
        {
            "error": error,
            "email": email,
            "next": request.GET.get("next") or request.POST.get("next") or "",
            "demo_accounts": [
                {
                    "email": account_email,
                    "password": account["password"],
                    "role": account["role"],
                    "role_label": mock_data.ROLE_LABELS[account["role"]],
                    "name": account["profile"]["name"],
                    "initials": account["profile"]["initials"],
                    "job_title": account["profile"]["job_title"],
                }
                for account_email, account in mock_data.DEMO_ACCOUNTS.items()
            ],
            "hide_nav": True,
        },
    )


def logout(request):
    """POST-only sign out. A stray GET redirects rather than erroring."""
    if request.method != "POST":
        return redirect("dashboard:landing")
    request.session.flush()
    return redirect(f"{reverse('dashboard:landing')}?signed_out=1")


@role_required()
def profile(request):
    """Account profile. Shared identity header plus a role-specific block.
    Only phone and location are editable; the edits live in the session."""
    if request.method == "POST":
        request.session["profile_phone"] = (request.POST.get("phone") or "").strip()
        request.session["profile_location"] = (request.POST.get("location") or "").strip()
        return redirect(f"{reverse('dashboard:profile')}?saved=1")

    role = request.session.get("role")
    context = {"saved": request.GET.get("saved") == "1"}

    if role == mock_data.ROLE_AGENT:
        points = mock_data.AGENT_PROFILE["points"]
        context["tier"] = mock_data.get_tier(points)
        context["next_tier"] = _progress(points)

    elif role == mock_data.ROLE_MANAGER:
        reports = mock_data.reports_for_manager(mock_data.MANAGER_PROFILE["id"])
        by_tier = {t["slug"]: 0 for t in mock_data.TIERS}
        for agent in reports:
            by_tier[mock_data.get_tier(agent["points"])["slug"]] += 1
        total_points = sum(a["points"] for a in reports)
        by_tenure = sorted(reports, key=lambda a: a["tenure_months"], reverse=True)
        context.update({
            "reports": reports,
            "team_points": total_points,
            "team_average_tier": mock_data.get_tier(round(total_points / len(reports))),
            "tier_counts": [
                {"tier": tier, "count": by_tier[tier["slug"]]} for tier in mock_data.TIERS
            ],
            "longest_tenured": by_tenure[:3],
            "newest": by_tenure[-3:][::-1],
        })

    elif role == mock_data.ROLE_DIRECTOR:
        budget = mock_data.DIRECTOR_PROFILE["annual_budget"]
        context["budget_display"] = f"${budget / 1_000_000:.1f}M"

    return render(request, "dashboard/profile.html", context)


def _prefs_from_session(request):
    """Merge stored overrides onto the mock defaults so a fresh session still
    renders a sensible state."""
    role = request.session.get("role", mock_data.ROLE_AGENT)
    stored = request.session.get("notification_prefs", {})
    groups = []
    for group in mock_data.NOTIFICATION_PREFS[role]:
        items = []
        for item in group["items"]:
            saved = stored.get(item["key"], {})
            items.append(dict(
                item,
                email=saved.get("email", item["email"]),
                push=saved.get("push", item["push"]),
            ))
        groups.append({"title": group["title"], "items": items})
    return groups


@role_required()
def notification_settings(request):
    """Autosaving notification preferences, stored in the session."""
    if request.method == "POST":
        try:
            payload = json.loads(request.body or b"{}")
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({"error": "Malformed JSON body."}, status=400)

        stored = request.session.get("notification_prefs", {})

        if "digest" in payload:
            if payload["digest"] not in mock_data.DIGEST_CHOICES:
                return JsonResponse({"error": "Unknown digest option."}, status=400)
            request.session["digest_frequency"] = payload["digest"]
        elif "mute_all" in payload:
            request.session["mute_all"] = bool(payload["mute_all"])
        else:
            key = payload.get("key")
            channel = payload.get("channel")
            role = request.session.get("role", mock_data.ROLE_AGENT)
            valid_keys = {
                i["key"] for g in mock_data.NOTIFICATION_PREFS[role] for i in g["items"]
            }
            if key not in valid_keys or channel not in ("email", "push"):
                return JsonResponse({"error": "Unknown preference."}, status=400)
            entry = dict(stored.get(key, {}))
            entry[channel] = bool(payload.get("value"))
            stored[key] = entry
            request.session["notification_prefs"] = stored

        return JsonResponse({"ok": True})

    return render(
        request,
        "dashboard/notifications.html",
        {
            "groups": _prefs_from_session(request),
            "digest_choices": mock_data.DIGEST_CHOICES,
            "digest_current": request.session.get("digest_frequency", mock_data.DIGEST_DEFAULT),
            "mute_all": request.session.get("mute_all", mock_data.MUTE_ALL_DEFAULT),
        },
    )


def _placeholder(request, title, blurb):
    return render(request, "dashboard/placeholder.html", {"title": title, "blurb": blurb})


@role_required(mock_data.ROLE_AGENT)
def log_work(request):
    return _placeholder(request, "Log Work",
                        "Submit jobs, hours and points for your manager to approve.")


@role_required(mock_data.ROLE_MANAGER)
def manager_team(request):
    return _placeholder(request, "Team",
                        "Roster, per-agent drill-down and workload signals for your technicians.")


@role_required(mock_data.ROLE_MANAGER)
def manager_programs(request):
    return _placeholder(request, "Programs",
                        "Build incentive programs and send them up for director sign-off.")


@role_required(mock_data.ROLE_MANAGER)
def manager_approvals(request):
    return _placeholder(request, "Approvals",
                        "Review the work logs your technicians have submitted.")


@role_required(mock_data.ROLE_DIRECTOR)
def director_overview(request):
    return _placeholder(request, "Overview",
                        "Territory rollups across every manager, team and warehouse.")


@role_required(mock_data.ROLE_DIRECTOR)
def director_programs(request):
    return _placeholder(request, "Programs",
                        "Every incentive program in the territory, with spend against budget.")


@role_required(mock_data.ROLE_DIRECTOR)
def director_approvals(request):
    return _placeholder(request, "Approvals",
                        "Programs awaiting your approval.")


@require_POST
def dev_reset_store(request):
    """Restore the in-memory store to its seed state so a demo restarts clean."""
    store.reset_store()
    return JsonResponse({"ok": True, "detail": "Store reset to seed state."})
