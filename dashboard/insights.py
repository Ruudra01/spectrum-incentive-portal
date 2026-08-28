"""Rule-based insight engine for the agent dashboard.

NOT an LLM and not the chatbot's keyword matcher — this is a fixed set of
conditions evaluated against the agent's own logged work. Every headline is
derived from data in store.py and mock_data.py, so nothing here can state a
figure the rest of the portal disagrees with.

Rules are evaluated in priority order and the top four that fire are shown.
"""

from datetime import date, datetime, timedelta

from . import mock_data, store

# Tones map onto existing UI treatments; no new colours are introduced.
TONE_OPPORTUNITY = "opportunity"
TONE_CAUTION = "caution"
TONE_CELEBRATION = "celebration"
TONE_INFORMATIONAL = "informational"

MAX_INSIGHTS = 4
TIER_PROXIMITY_POINTS = 500
STREAK_MIN_DAYS = 3
MODIFIER_WINDOW_DAYS = 14
REWARD_MODIFIERS = ("premium_upsell", "first_time_fix")


def _parse(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _approved_streak(entries, today):
    """Consecutive days, ending at the most recent approved day, with work."""
    days = {_parse(e["date"]) for e in entries if e["status"] == store.STATUS_APPROVED}
    days.discard(None)
    if not days:
        return 0
    latest = max(days)
    # A streak that ended more than a day ago is not "running".
    if (today - latest).days > 1:
        return 0
    streak = 0
    cursor = latest
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _tier_proximity(agent, entries, today):
    progress = mock_data.points_to_next_tier(agent["points"])
    if progress is None:
        return None
    name, needed, _percent = progress
    if needed > TIER_PROXIMITY_POINTS:
        return None

    # Same math the what-if simulator uses.
    job = mock_data.JOB_TYPES_BY_CODE["new_install_residential"]
    jobs_needed = -(-needed // job["base_points"])
    return {
        "icon": "target",
        "tone": TONE_OPPORTUNITY,
        "headline": f"You're {needed} points from {name}",
        "detail": (f"About {jobs_needed} more residential install"
                   f"{'s' if jobs_needed != 1 else ''} at current rates."),
        "cta_label": "Log a job",
        "cta_url": "/log-work/",
    }


def _streak(agent, entries, today):
    streak = _approved_streak(entries, today)
    if streak < STREAK_MIN_DAYS:
        return None
    return {
        "icon": "flame",
        "tone": TONE_CELEBRATION,
        "headline": f"{streak} days running with approved work",
        "detail": "You've kept an unbroken run of approved jobs. Keep it going.",
        "cta_label": "View history",
        "cta_url": "/log-work/",
    }


def _changes_requested(agent, entries, today):
    waiting = [e for e in entries if e["status"] == store.STATUS_CHANGES]
    if not waiting:
        return None
    oldest = min(waiting, key=lambda e: e["date"])
    count = len(waiting)
    return {
        "icon": "alert",
        "tone": TONE_CAUTION,
        "headline": f"{count} entr{'y' if count == 1 else 'ies'} waiting on your edits",
        "detail": "Your manager asked for changes before these can be approved.",
        "cta_label": "Review now",
        "cta_url": f"/log-work/?date={oldest['date']}",
    }


def _modifier_opportunity(agent, entries, today):
    cutoff = today - timedelta(days=MODIFIER_WINDOW_DAYS)
    recent = [e for e in entries if (_parse(e["date"]) or today) >= cutoff]
    if not recent:
        return None
    if any(m in REWARD_MODIFIERS for e in recent for m in e["modifiers"]):
        return None

    upsell = mock_data.POINT_MODIFIERS_BY_CODE["premium_upsell"]
    percent = int(upsell["multiplier"] * 100)
    return {
        "icon": "spark",
        "tone": TONE_INFORMATIONAL,
        "headline": "No premium upsell logged in two weeks",
        "detail": f"A premium add-on adds {percent}% to a job's points.",
        "cta_label": "See how points work",
        "cta_url": "/faqs/",
    }


def _pending_value(agent, entries, today):
    summary = store.agent_points_summary(agent["id"])
    points = summary["pending_points"]
    if points <= 0:
        return None
    return {
        "icon": "clock",
        "tone": TONE_INFORMATIONAL,
        "headline": f"{points} points awaiting approval",
        "detail": (f"Worth ${mock_data.points_to_usd(points):,.2f} once your "
                   "manager signs off."),
        "cta_label": "",
        "cta_url": "",
    }


def _program_match(agent, entries, today):
    """Active-program nudge.

    Programs carry no job-type targeting in this build, so this rule skips
    gracefully until that field exists rather than inventing a match.
    """
    week_start = today - timedelta(days=7)
    for program in store.get_programs(status=store.PROGRAM_APPROVED):
        if program.get("team") != agent.get("team"):
            continue
        qualifying = program.get("job_types")
        if not qualifying:
            continue
        logged = {e["job_type"] for e in entries
                  if (_parse(e["date"]) or today) >= week_start}
        if logged & set(qualifying):
            continue
        return {
            "icon": "target",
            "tone": TONE_OPPORTUNITY,
            "headline": f"{program['name']} is running",
            "detail": (f"Qualifying jobs pay {program['multiplier']}x through "
                       f"{program['ends']}."),
            "cta_label": "Log a job",
            "cta_url": "/log-work/",
        }
    return None


# Priority order — the first four that fire are shown.
RULES = (
    _tier_proximity,
    _streak,
    _changes_requested,
    _modifier_opportunity,
    _pending_value,
    _program_match,
)

FALLBACK = {
    "icon": "spark",
    "tone": TONE_INFORMATIONAL,
    "headline": "You're on track",
    "detail": "Check back after your next approved job for new insights.",
    "cta_label": "",
    "cta_url": "",
    "is_fallback": True,
}


def generate_insights(agent_id, today=None):
    """Ranked insights for one agent. Returns at most MAX_INSIGHTS."""
    agent = mock_data.get_agent(agent_id) or mock_data.AGENT_PROFILE
    # get_agent returns a leaderboard row; fold in the points the profile holds.
    agent = dict(agent)
    agent.setdefault("team", mock_data.AGENT_PROFILE.get("team"))
    today = today or date.today()
    entries = store.get_entries_for_agent(agent_id)

    insights = []
    for rule in RULES:
        result = rule(agent, entries, today)
        if result:
            insights.append(result)
        if len(insights) == MAX_INSIGHTS:
            break

    if len(insights) < 2:
        insights.append(dict(FALLBACK))
    return insights


if __name__ == "__main__":
    import os, django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spectrum_portal.settings")
    django.setup()

    store.reset_store()
    today = date.today()
    results = generate_insights(417, today)
    assert 2 <= len(results) <= MAX_INSIGHTS, len(results)
    for item in results:
        assert item["tone"] in (TONE_OPPORTUNITY, TONE_CAUTION,
                                TONE_CELEBRATION, TONE_INFORMATIONAL)
        assert item["headline"] and item["detail"]
    print("insights OK —", len(results), "for Dana:")
    for item in results:
        print(f"  [{item['tone']:<14}] {item['headline']}")
