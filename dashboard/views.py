import json
from datetime import date

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import chat_responses, insights, mock_data, store
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
    today = date.today().isoformat()
    today_summary = store.get_day_summary(agent["id"], today)
    points_summary = store.agent_points_summary(agent["id"])
    ledger = {
        "approved_points": points_summary["approved_points"],
        "approved_usd": mock_data.points_to_usd(points_summary["approved_points"]),
        "pending_points": points_summary["pending_points"],
        "pending_usd": mock_data.points_to_usd(points_summary["pending_points"]),
    }

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
            # Ledger
            "ledger": ledger,
            "today_summary": today_summary,
            "insights": insights.generate_insights(agent["id"]),
            "point_value": mock_data.POINT_VALUE_USD,
            "next_payout": mock_data.NEXT_PAYOUT_DATE,
            # Simulator mirrors the same job/tier numbers the server uses.
            "sim_data": json.dumps({
                "points": agent["points"],
                "rate": mock_data.POINT_VALUE_USD,
                "tiers": [
                    {"name": t["name"], "slug": t["slug"], "min": t["min_points"]}
                    for t in mock_data.TIERS
                ],
                "jobs": [
                    {"code": j["code"], "label": j["label"], "points": j["base_points"]}
                    for j in mock_data.JOB_TYPES
                ],
            }),
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


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _agent_ctx(request):
    """The signed-in agent's identity, straight from DEMO_ACCOUNTS."""
    account = mock_data.DEMO_ACCOUNTS[request.session["user_email"]]
    return account["profile"]


@role_required(mock_data.ROLE_AGENT)
def log_work(request):
    """Daily work log. One endpoint handles add / edit / delete / submit."""
    agent = _agent_ctx(request)
    today = date.today().isoformat()

    if request.method == "POST":
        action = request.POST.get("action")
        # Future days can't be logged; clamp anything the client sends.
        on_date = (request.POST.get("date") or today)[:10]
        if on_date > today:
            on_date = today
        back = f"{reverse('dashboard:log_work')}?date={on_date}"

        if action == "submit_day":
            count, points = store.submit_day(agent["id"], on_date)
            if count:
                return redirect(f"{back}&submitted={count}&pts={points}")
            return redirect(back)

        if action == "delete":
            store.delete_entry(_int(request.POST.get("entry_id")), agent["id"])
            return redirect(f"{back}&deleted=1")

        # add / update share the same cleaned payload
        fields = {
            "job_type": request.POST.get("job_type", ""),
            "work_order_ref": (request.POST.get("work_order_ref") or "").strip()[:32],
            "address_line": (request.POST.get("address_line") or "").strip()[:120],
            "duration_minutes": max(0, min(_int(request.POST.get("duration_minutes")), 1440)),
            "modifiers": [m for m in request.POST.getlist("modifiers")
                          if m in mock_data.POINT_MODIFIERS_BY_CODE],
            "notes": (request.POST.get("notes") or "").strip()[:280],
        }
        if fields["job_type"] not in mock_data.JOB_TYPES_BY_CODE:
            return redirect(f"{back}&error=job")

        if action == "update":
            store.update_entry(_int(request.POST.get("entry_id")), agent["id"], **fields)
            return redirect(f"{back}&saved=1")

        # Points are computed in the store, never taken from the form.
        store.add_entry(
            agent["id"], agent["name"], agent["manager_id"], on_date,
            status=(store.STATUS_SUBMITTED if action == "add_submit" else store.STATUS_DRAFT),
            **fields,
        )
        return redirect(f"{back}&saved=1")

    # --- GET ---
    on_date = (request.GET.get("date") or today)[:10]
    if on_date > today:
        on_date = today

    entries = store.get_entries_for_agent(agent["id"], on_date)
    for entry in entries:
        entry["job"] = mock_data.JOB_TYPES_BY_CODE.get(entry["job_type"], {})
        entry["modifier_details"] = [
            mock_data.POINT_MODIFIERS_BY_CODE[m] for m in entry["modifiers"]
            if m in mock_data.POINT_MODIFIERS_BY_CODE
        ]
        entry["status_label"] = store.STATUS_LABELS.get(entry["status"], entry["status"])
        entry["editable"] = entry["status"] in store.EDITABLE_STATUSES
        entry["reviewer_name"] = mock_data.MANAGER_PROFILE["name"] if entry["reviewer_id"] else ""

    summary = store.get_day_summary(agent["id"], on_date)

    return render(request, "dashboard/log_work.html", {
        "on_date": on_date,
        "today": today,
        "entries": entries,
        "summary": summary,
        "job_types": mock_data.JOB_TYPES,
        "job_groups": [
            {"name": group,
             "jobs": [j for j in mock_data.JOB_TYPES if j["group"] == group]}
            for group in mock_data.JOB_TYPE_GROUPS
        ],
        "modifiers": [m for m in mock_data.POINT_MODIFIERS
                      if m["code"] != mock_data.SAFETY_MODIFIER],
        "safety_modifier": mock_data.POINT_MODIFIERS_BY_CODE[mock_data.SAFETY_MODIFIER],
        # The browser mirrors calculate_points from this, so the two can't drift.
        "calc_data": json.dumps({
            "jobs": {j["code"]: j["base_points"] for j in mock_data.JOB_TYPES},
            "minutes": {j["code"]: j["est_minutes"] for j in mock_data.JOB_TYPES},
            "modifiers": {m["code"]: m["multiplier"] for m in mock_data.POINT_MODIFIERS},
            "safety": mock_data.SAFETY_MODIFIER,
        }),
        "manager_name": mock_data.MANAGER_PROFILE["name"],
        "saved": request.GET.get("saved") == "1",
        "deleted": request.GET.get("deleted") == "1",
        "submitted_count": _int(request.GET.get("submitted")),
    })



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
