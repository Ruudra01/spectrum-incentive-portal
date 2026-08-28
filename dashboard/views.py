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


def _hours_since(stamp):
    """Hours since a "YYYY-MM-DD HH:MM" stamp, or None if unparseable."""
    from datetime import datetime
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return (datetime.now() - datetime.strptime(stamp, fmt)).total_seconds() / 3600
        except (TypeError, ValueError):
            continue
    return None


def _age_label(hours):
    if hours is None:
        return ""
    if hours < 1:
        return "submitted just now"
    if hours < 24:
        return f"submitted {int(hours)} hour{'s' if int(hours) != 1 else ''} ago"
    return f"submitted {int(hours // 24)} day{'s' if int(hours // 24) != 1 else ''} ago"


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






def _manager(request):
    return mock_data.DEMO_ACCOUNTS[request.session["user_email"]]["profile"]


@role_required(mock_data.ROLE_MANAGER)
def manager_team(request):
    """Team dashboard: KPIs, burnout watch, roster and the 12-week trend."""
    manager = _manager(request)
    stats = store.get_team_stats(manager["id"])
    signals = store.get_burnout_signals(manager["id"])
    reports = mock_data.reports_for_manager(manager["id"])

    pending_by_agent = {}
    for entry in store.get_submitted_for_manager(manager["id"]):
        pending_by_agent[entry["agent_id"]] = pending_by_agent.get(entry["agent_id"], 0) + 1
    flagged = {s["agent"]["id"] for s in signals}

    roster = []
    for agent in reports:
        roster.append(dict(
            agent,
            tier=mock_data.get_tier(agent["points"]),
            initials="".join(w[0] for w in agent["name"].split()[:2]).upper(),
            pending=pending_by_agent.get(agent["id"], 0),
            flagged=agent["id"] in flagged,
            over_overtime=agent["overtime_hours_this_week"] > mock_data.BURNOUT_OVERTIME_HOURS,
            # Widths for the inline data bars, relative to the team average.
            repeat_pct=min(round(agent["repeat_rate"] / max(stats["repeat_rate"], 0.1) * 50), 100),
            on_time_pct=min(round(agent["on_time_rate"] / max(stats["on_time_rate"], 0.1) * 50), 100),
            recent=store.get_entries_for_agent(agent["id"])[:5],
            spark=mock_data.agent_weekly_points(agent),
        ))

    for row in roster:
        for entry in row["recent"]:
            entry["job_label"] = mock_data.JOB_TYPES_BY_CODE.get(
                entry["job_type"], {}).get("label", entry["job_type"])
            entry["status_label"] = store.STATUS_LABELS.get(entry["status"], entry["status"])

    return render(request, "dashboard/manager_team.html", {
        "stats": stats,
        "signals": signals[:5],
        "signal_total": len(signals),
        "all_signals": signals,
        "roster": roster,
        "tiers": mock_data.TIERS,
        "burnout_rules": {
            "overtime": mock_data.BURNOUT_OVERTIME_HOURS,
            "days": mock_data.BURNOUT_CONSECUTIVE_DAYS,
            "margin": mock_data.BURNOUT_REPEAT_RATE_MARGIN,
        },
        "trend": json.dumps({
            "weeks": mock_data.TEAM_WEEKLY_POINTS,
            "sparks": {str(r["id"]): r["spark"] for r in roster},
        }),
    })


def _group_key(entry):
    return f"{entry['agent_id']}:{entry['date']}"


@role_required(mock_data.ROLE_MANAGER)
def manager_approvals(request):
    """Two-pane review queue. Rejections and change requests need a note."""
    manager = _manager(request)

    if request.method == "POST":
        if request.POST.get("action") == "reopen":
            store.reopen_entry(_int(request.POST.get("entry_id")), manager["id"],
                               request.POST.get("note", ""))
            return redirect(f"{reverse('dashboard:manager_approvals')}?reopened=1")

        decisions = []
        for key in request.POST:
            if not key.startswith("decision_"):
                continue
            entry_id = _int(key.split("_", 1)[1])
            status = request.POST.get(key)
            if status in (store.STATUS_APPROVED, store.STATUS_REJECTED, store.STATUS_CHANGES):
                decisions.append({
                    "entry_id": entry_id,
                    "status": status,
                    "note": request.POST.get(f"note_{entry_id}", ""),
                })
        applied, refused = store.review_batch(decisions, manager["id"])
        agent_name = request.POST.get("agent_name", "the agent")
        target = f"{reverse('dashboard:manager_approvals')}?done={len(applied)}"
        if refused:
            target += f"&refused={len(refused)}"
        if applied:
            target += f"&who={agent_name}"
        return redirect(target)

    queue = store.get_submitted_for_manager(manager["id"])
    groups = {}
    for entry in queue:
        entry["job"] = mock_data.JOB_TYPES_BY_CODE.get(entry["job_type"], {})
        entry["modifier_details"] = [
            dict(mock_data.POINT_MODIFIERS_BY_CODE[m],
                 material=m in ("adverse_weather", "premium_upsell", "after_hours"))
            for m in entry["modifiers"] if m in mock_data.POINT_MODIFIERS_BY_CODE
        ]
        key = _group_key(entry)
        group = groups.setdefault(key, {
            "key": key, "agent_id": entry["agent_id"], "agent_name": entry["agent_name"],
            "initials": "".join(w[0] for w in entry["agent_name"].split()[:2]).upper(),
            "date": entry["date"], "submitted_at": entry["submitted_at"],
            "entries": [], "points": 0,
        })
        group["entries"].append(entry)
        group["points"] += entry["points"]

    groups = list(groups.values())
    sort = request.GET.get("sort", "oldest")
    keys = {
        "oldest": lambda g: (g["submitted_at"] or "", g["agent_name"]),
        "newest": lambda g: (g["submitted_at"] or "", g["agent_name"]),
        "points": lambda g: -g["points"],
        "agent": lambda g: g["agent_name"],
    }
    groups.sort(key=keys.get(sort, keys["oldest"]), reverse=(sort == "newest"))

    for group in groups:
        group["age_hours"] = _hours_since(group["submitted_at"])
        group["stale"] = group["age_hours"] is not None and group["age_hours"] > 48
        group["age_label"] = _age_label(group["age_hours"])

    selected_key = request.GET.get("g") or (groups[0]["key"] if groups else None)
    selected = next((g for g in groups if g["key"] == selected_key), None)

    today = date.today().isoformat()
    history = store.get_reviewed_by(manager["id"])
    for entry in history:
        entry["job_label"] = mock_data.JOB_TYPES_BY_CODE.get(
            entry["job_type"], {}).get("label", entry["job_type"])
        entry["status_label"] = store.STATUS_LABELS.get(entry["status"], entry["status"])
        entry["reopenable"] = (_hours_since(entry["reviewed_at"]) or 999) <= store.REOPEN_WINDOW_HOURS

    return render(request, "dashboard/manager_approvals.html", {
        "groups": groups,
        "selected": selected,
        "sort": sort,
        "queue_count": len(queue),
        "history": history[:20],
        "reviewed_today": sum(1 for e in history if (e["reviewed_at"] or "").startswith(today)),
        "done": _int(request.GET.get("done")),
        "refused": _int(request.GET.get("refused")),
        "who": request.GET.get("who", ""),
        "reopened": request.GET.get("reopened") == "1",
    })


@role_required(mock_data.ROLE_MANAGER)
def manager_programs(request):
    """List and author incentive programs."""
    manager = _manager(request)

    if request.method == "POST":
        rules = []
        for count, job, bonus in zip(request.POST.getlist("rule_count"),
                                     request.POST.getlist("rule_job"),
                                     request.POST.getlist("rule_bonus")):
            if job in mock_data.JOB_TYPES_BY_CODE and _int(count) > 0:
                rules.append({"count": _int(count), "job_type": job, "bonus": _int(bonus)})

        fields = {
            "name": (request.POST.get("name") or "").strip()[:120],
            "description": (request.POST.get("description") or "").strip()[:600],
            "start_date": (request.POST.get("start_date") or "")[:10],
            "end_date": (request.POST.get("end_date") or "")[:10],
            "target_scope": request.POST.get("target_scope", "team"),
            "target_team": manager["team"],
            "job_types": [j for j in request.POST.getlist("job_types")
                          if j in mock_data.JOB_TYPES_BY_CODE],
            "bonus_structure": rules,
            "expected_participants": _int(request.POST.get("expected_participants")),
            "budget_estimate": _int(request.POST.get("budget_estimate")),
            "success_metric": request.POST.get("success_metric", ""),
            "success_target": _int(request.POST.get("success_target")),
        }
        # End must follow start; refuse rather than store an impossible range.
        if fields["end_date"] and fields["start_date"] and fields["end_date"] < fields["start_date"]:
            return redirect(f"{reverse('dashboard:manager_programs')}?error=dates")

        program_id = _int(request.POST.get("program_id"))
        if program_id:
            store.update_program(program_id, manager["id"], **fields)
        else:
            program = store.create_program(manager["id"], manager["name"], **fields)
            program_id = program["id"]

        if request.POST.get("action") == "submit":
            store.submit_program(program_id, manager["id"])
            return redirect(f"{reverse('dashboard:manager_programs')}?submitted=1")
        return redirect(f"{reverse('dashboard:manager_programs')}?saved=1")

    programs = store.get_programs_for_manager(manager["id"])
    today = date.today().isoformat()
    for program in programs:
        program["metric_label"] = mock_data.SUCCESS_METRICS_BY_CODE.get(
            program["success_metric"], {}).get("label", "—")
        if program["status"] == store.PROGRAM_APPROVED:
            if program["start_date"] > today:
                program["phase"] = "Scheduled"
            elif program["end_date"] < today:
                program["phase"] = "Ended"
            else:
                program["phase"] = "Active"
        else:
            program["phase"] = ""

    editing = None
    edit_id = _int(request.GET.get("edit"))
    if edit_id:
        candidate = store.get_program(edit_id)
        if candidate and candidate["created_by"] == manager["id"]:
            editing = candidate

    return render(request, "dashboard/manager_programs.html", {
        "programs": programs,
        "editing": editing,
        "creating": request.GET.get("new") == "1" or editing is not None,
        "job_types": mock_data.JOB_TYPES,
        "job_groups": [{"name": g, "jobs": [j for j in mock_data.JOB_TYPES if j["group"] == g]}
                       for g in mock_data.JOB_TYPE_GROUPS],
        "metrics": mock_data.SUCCESS_METRICS,
        "scopes": mock_data.PROGRAM_SCOPES,
        "point_value": mock_data.POINT_VALUE_USD,
        "editable_statuses": list(store.EDITABLE_PROGRAM_STATUSES),
        "saved": request.GET.get("saved") == "1",
        "submitted": request.GET.get("submitted") == "1",
        "date_error": request.GET.get("error") == "dates",
    })


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
