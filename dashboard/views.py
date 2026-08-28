import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import chat_responses, mock_data
from .decorators import agent_required


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
    """Session-only sign in against the demo credentials. No auth app."""
    if request.session.get("is_authenticated"):
        return redirect("dashboard:dashboard")

    error = None
    email = ""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""
        if (
            email.lower() == mock_data.DEMO_EMAIL.lower()
            and password == mock_data.DEMO_PASSWORD
        ):
            request.session["is_authenticated"] = True
            request.session["agent_name"] = mock_data.CURRENT_AGENT["name"]
            return redirect(_safe_next(request.POST.get("next")) or reverse("dashboard:dashboard"))
        # Deliberately non-specific: never reveal which field was wrong.
        error = "The email or password you entered is incorrect."

    return render(
        request,
        "dashboard/login.html",
        {
            "error": error,
            "email": email,
            "next": _safe_next(request.GET.get("next") or request.POST.get("next")) or "",
            "demo_email": mock_data.DEMO_EMAIL,
            "demo_password": mock_data.DEMO_PASSWORD,
            "hide_nav": True,
        },
    )


def logout(request):
    """POST-only sign out. A stray GET redirects rather than erroring."""
    if request.method != "POST":
        return redirect("dashboard:landing")
    request.session.flush()
    return redirect(f"{reverse('dashboard:landing')}?signed_out=1")


@agent_required
def profile(request):
    """Account profile. Only phone and location are editable; the edits live
    in the session so they persist without a database."""
    if request.method == "POST":
        request.session["profile_phone"] = (request.POST.get("phone") or "").strip()
        request.session["profile_location"] = (request.POST.get("location") or "").strip()
        return redirect(f"{reverse('dashboard:profile')}?saved=1")

    points = mock_data.PROFILE_DATA["points"]
    return render(
        request,
        "dashboard/profile.html",
        {
            "tier": mock_data.get_tier(points),
            "next_tier": _progress(points),
            "saved": request.GET.get("saved") == "1",
        },
    )


def _prefs_from_session(request):
    """Merge stored overrides onto the mock defaults so a fresh session still
    renders a sensible state."""
    stored = request.session.get("notification_prefs", {})
    groups = []
    for group in mock_data.NOTIFICATION_PREFS:
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


@agent_required
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
            valid_keys = {i["key"] for g in mock_data.NOTIFICATION_PREFS for i in g["items"]}
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
