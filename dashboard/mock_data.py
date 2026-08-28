"""Static reference data for the portal.

This module holds things that do NOT change at runtime: tiers and thresholds,
KPI definitions, the org chart, demo accounts and notification defaults.
Anything mutable — work logs, programs, approvals — lives in store.py.
"""

import math

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
ROLE_AGENT = "agent"
ROLE_MANAGER = "manager"
ROLE_DIRECTOR = "director"

ROLE_LABELS = {
    ROLE_AGENT: "Field Agent",
    ROLE_MANAGER: "Manager",
    ROLE_DIRECTOR: "Director",
}

ROLE_HOME = {
    ROLE_AGENT: "dashboard:dashboard",
    ROLE_MANAGER: "dashboard:manager_team",
    ROLE_DIRECTOR: "dashboard:director_overview",
}

# ---------------------------------------------------------------------------
# Tiers
# ---------------------------------------------------------------------------
TIERS = [
    {
        "name": "Bronze",
        "slug": "bronze",
        "min_points": 0,
        "max_points": 2499,
        "perks": [
            "Weekly points statement",
            "Standard install queue",
            "Base upsell commission",
        ],
    },
    {
        "name": "Silver",
        "slug": "silver",
        "min_points": 2500,
        "max_points": 4999,
        "perks": [
            "Priority install routing",
            "1.25x upsell commission",
            "Quarterly gear credit",
        ],
    },
    {
        "name": "Gold",
        "slug": "gold",
        "min_points": 5000,
        "max_points": None,
        "perks": [
            "First pick of premium routes",
            "1.5x upsell commission",
            "Annual recognition summit",
        ],
    },
]


def get_tier(points):
    """Return the tier dict a point total falls into."""
    for tier in reversed(TIERS):
        if points >= tier["min_points"]:
            return tier
    return TIERS[0]


def points_to_next_tier(points):
    """Return (next_tier_name, points_needed, percent_through_current_tier).

    Returns None at the top tier, which has no next tier to climb to.
    """
    current = get_tier(points)
    index = TIERS.index(current)
    if index == len(TIERS) - 1:
        return None
    following = TIERS[index + 1]
    span = following["min_points"] - current["min_points"]
    percent = round((points - current["min_points"]) / span * 100)
    return following["name"], following["min_points"] - points, percent


# ---------------------------------------------------------------------------
# DEMO CREDENTIALS — frontend prototype only.
# Hardcoded on purpose so a reviewer can sign in as each role without a
# database. Passwords are compared in plain text. Replace with a real auth
# backend (hashed passwords, a user store, rate limiting) before any non-demo
# use. Do not deploy this as-is.
# ---------------------------------------------------------------------------
DEMO_PASSWORD = "spectrum2026"

AGENT_PROFILE = {
    "id": 417,
    "email": "agent@spectrum.com",
    "name": "Dana Whitfield",
    "initials": "DW",
    "employee_id": "EMP-40271",
    "job_title": "Field Installation Technician",
    "region": "Ohio Valley",
    "team": "Columbus North",
    "manager_name": "Marcus Vale",
    "manager_id": 884,
    "location": "Columbus, OH",
    "hire_date": "2023-03-14",
    "phone": "(614) 555-0142",
    # Performance — unchanged so the existing dashboard renders identically.
    "points": 3180,
    "rank": 4,
    "points_this_week": 240,
}

MANAGER_PROFILE = {
    "id": 884,
    "email": "manager@spectrum.com",
    "name": "Marcus Vale",
    "initials": "MV",
    "employee_id": "EMP-31884",
    "job_title": "Field Operations Manager",
    "region": "Ohio Valley",
    "team": "Columbus North",
    "manager_name": "Priya Raghunathan",
    "manager_id": 115,
    "location": "Columbus, OH",
    "hire_date": "2019-08-05",
    "phone": "(614) 555-0188",
    "team_size": 18,
    "warehouse": "Columbus North Depot",
    "years_in_role": 4,
}

DIRECTOR_PROFILE = {
    "id": 115,
    "email": "director@spectrum.com",
    "name": "Priya Raghunathan",
    "initials": "PR",
    "employee_id": "EMP-20115",
    "job_title": "Director of Field Operations",
    "region": "Great Lakes Territory",
    "team": "Field Operations",
    "manager_name": "VP Field Operations",
    "manager_id": None,
    "location": "Cleveland, OH",
    "hire_date": "2015-01-20",
    "phone": "(216) 555-0110",
    "managers_count": 6,
    "technicians_count": 142,
    "warehouses": 4,
    "annual_budget": 8_400_000,
    "region_nps": 41,
    "retention_rate": 88.5,
}

DEMO_ACCOUNTS = {
    "agent@spectrum.com": {
        "password": DEMO_PASSWORD,
        "role": ROLE_AGENT,
        "profile": AGENT_PROFILE,
    },
    "manager@spectrum.com": {
        "password": DEMO_PASSWORD,
        "role": ROLE_MANAGER,
        "profile": MANAGER_PROFILE,
    },
    "director@spectrum.com": {
        "password": DEMO_PASSWORD,
        "role": ROLE_DIRECTOR,
        "profile": DIRECTOR_PROFILE,
    },
}

# Backwards-compatible aliases for the agent-only views built earlier.
CURRENT_AGENT = AGENT_PROFILE
PROFILE_DATA = AGENT_PROFILE
DEMO_EMAIL = AGENT_PROFILE["email"]

# ---------------------------------------------------------------------------
# Org chart: Priya -> 6 managers -> Marcus supervises 18 technicians
# ---------------------------------------------------------------------------
ORG = {
    "director": {"id": 115, "name": "Priya Raghunathan", "region": "Great Lakes Territory"},
    "managers": [
        {"id": 884, "name": "Marcus Vale", "team": "Columbus North",
         "region": "Ohio Valley", "team_size": 18, "is_demo_user": True},
        {"id": 885, "name": "Deirdre Kwan", "team": "Cleveland East",
         "region": "Ohio Valley", "team_size": 24, "is_demo_user": False},
        {"id": 886, "name": "Hollis Barrera", "team": "Toledo West",
         "region": "Ohio Valley", "team_size": 21, "is_demo_user": False},
        {"id": 887, "name": "Nadia Petrov", "team": "Indianapolis Metro",
         "region": "Great Lakes", "team_size": 26, "is_demo_user": False},
        {"id": 888, "name": "Curtis Amankwah", "team": "Detroit North",
         "region": "Great Lakes", "team_size": 27, "is_demo_user": False},
        {"id": 889, "name": "Yusuf Demir", "team": "Grand Rapids",
         "region": "Great Lakes", "team_size": 26, "is_demo_user": False},
    ],
}

# ---------------------------------------------------------------------------
# Marcus Vale's 18 technicians. Ordered by points, so rank == index + 1.
# The numbers tell a coherent story: longer tenure trends toward more points,
# better on-time and lower repeat rates. Two agents (Ibrahim, Sofia) break the
# pattern with heavy overtime and depressed CSAT — the burnout signal the
# manager views are built to surface.
# ---------------------------------------------------------------------------
def _agent(id, name, region, points, rank, repeat_rate, on_time_rate, jobs,
           overtime, safety, csat, tenure):
    return {
        "id": id, "name": name, "region": region, "points": points, "rank": rank,
        "manager_id": 884, "team": "Columbus North",
        "repeat_rate": repeat_rate, "on_time_rate": on_time_rate,
        "jobs_this_week": jobs, "overtime_hours_this_week": overtime,
        "safety_audits_passed": safety, "csat": csat, "tenure_months": tenure,
    }


LEADERBOARD = [
    _agent(902, "Marcus Bell", "Ohio Valley", 6420, 1, 3.1, 97.5, 14, 2.0, 6, 4.9, 74),
    _agent(655, "Priya Raman", "Ohio Valley", 5730, 2, 3.8, 96.2, 13, 3.5, 6, 4.8, 61),
    _agent(731, "Alonzo Reyes", "Ohio Valley", 4310, 3, 4.6, 94.8, 12, 5.0, 5, 4.7, 48),
    _agent(417, "Dana Whitfield", "Ohio Valley", 3180, 4, 5.2, 93.1, 11, 6.5, 5, 4.6, 41),
    _agent(288, "Grace Okonkwo", "Ohio Valley", 2960, 5, 5.9, 92.4, 11, 7.0, 5, 4.5, 36),
    _agent(540, "Tomas Lindqvist", "Ohio Valley", 2740, 6, 6.4, 91.0, 10, 8.5, 4, 4.4, 33),
    _agent(119, "Renee Baptiste", "Ohio Valley", 2510, 7, 7.1, 90.2, 10, 9.0, 4, 4.3, 29),
    _agent(803, "Ibrahim Cole", "Ohio Valley", 2280, 8, 8.8, 87.5, 12, 14.5, 3, 3.9, 26),
    _agent(366, "Hana Fujimoto", "Ohio Valley", 2080, 9, 7.6, 89.4, 9, 9.5, 4, 4.2, 24),
    _agent(474, "Wesley Adjei", "Ohio Valley", 1900, 10, 8.2, 88.6, 9, 10.0, 4, 4.1, 21),
    _agent(521, "Sofia Marchetti", "Ohio Valley", 1815, 11, 9.4, 86.9, 11, 15.5, 3, 3.8, 19),
    _agent(638, "Darnell Pruitt", "Ohio Valley", 1690, 12, 9.0, 87.2, 8, 11.0, 3, 4.0, 17),
    _agent(712, "Aisha Nwosu", "Ohio Valley", 1540, 13, 9.8, 85.7, 8, 11.5, 3, 3.9, 14),
    _agent(845, "Victor Salazar", "Ohio Valley", 1420, 14, 10.5, 84.9, 8, 12.0, 2, 3.8, 12),
    _agent(957, "Mei-Ling Chow", "Ohio Valley", 1285, 15, 11.2, 83.6, 7, 12.5, 2, 3.7, 9),
    _agent(163, "Owen Brady", "Ohio Valley", 1120, 16, 12.0, 82.4, 7, 13.0, 2, 3.6, 7),
    _agent(279, "Tasha Greenwood", "Ohio Valley", 960, 17, 12.9, 81.0, 6, 13.5, 1, 3.5, 5),
    _agent(384, "Rafael Ortiz", "Ohio Valley", 720, 18, 13.6, 79.8, 6, 14.0, 1, 3.4, 3),
]

MANAGER_PROFILE["direct_report_ids"] = [a["id"] for a in LEADERBOARD]

# ---------------------------------------------------------------------------
# Agent dashboard figures
# ---------------------------------------------------------------------------
# The fourth dashboard tile is "Earned today", computed live from
# store.get_day_summary rather than being a static figure here.
KPI_STATS = [
    {"label": "Installs this month", "value": 38, "unit": "", "delta": 12.5, "direction": "up"},
    {"label": "Upsell conversion", "value": 24.8, "unit": "%", "delta": 3.1, "direction": "up"},
    {"label": "Points this week", "value": 240, "unit": "pts", "delta": 18.0, "direction": "up"},
]

WEEKLY_POINTS = [180, 205, 160, 240, 275, 210, 255, 240]

HEADLINE_STAT = {
    "label": "Points awarded to field agents this quarter",
    "value": sum(agent["points"] for agent in LEADERBOARD),
    "unit": "pts",
}


# ---------------------------------------------------------------------------
# Work logging: job types, point modifiers, and the one point calculation
# ---------------------------------------------------------------------------
JOB_TYPES = [
    {"code": "new_install_residential", "label": "New install — residential",
     "group": "Installs", "base_points": 120, "est_minutes": 90},
    {"code": "new_install_commercial", "label": "New install — commercial",
     "group": "Installs", "base_points": 180, "est_minutes": 150},
    {"code": "service_repair", "label": "Service repair",
     "group": "Repairs", "base_points": 80, "est_minutes": 60},
    {"code": "signal_troubleshoot", "label": "Signal troubleshoot",
     "group": "Repairs", "base_points": 90, "est_minutes": 75},
    {"code": "equipment_swap", "label": "Equipment swap",
     "group": "Repairs", "base_points": 50, "est_minutes": 30},
    {"code": "upgrade_premium_router", "label": "Premium router upgrade",
     "group": "Repairs", "base_points": 70, "est_minutes": 40},
    {"code": "aerial_line_work", "label": "Aerial line work",
     "group": "Line work", "base_points": 140, "est_minutes": 120},
    {"code": "underground_drop", "label": "Underground drop",
     "group": "Line work", "base_points": 130, "est_minutes": 110},
    {"code": "customer_education", "label": "Customer education",
     "group": "Customer", "base_points": 30, "est_minutes": 20},
]

JOB_TYPES_BY_CODE = {j["code"]: j for j in JOB_TYPES}

# Render order for the grouped <select>.
JOB_TYPE_GROUPS = ["Installs", "Repairs", "Line work", "Customer"]

POINT_MODIFIERS = [
    {"code": "first_time_fix", "label": "First-time fix", "multiplier": 0.15,
     "description": "Resolved without a follow-up visit."},
    {"code": "premium_upsell", "label": "Premium upsell", "multiplier": 0.25,
     "description": "Customer took a premium add-on."},
    {"code": "after_hours", "label": "After hours", "multiplier": 0.20,
     "description": "Completed outside the standard window."},
    {"code": "adverse_weather", "label": "Weather protected", "multiplier": 0.15,
     "description": "Storm, snow or extreme heat — pay is protected, not penalised."},
    {"code": "safety_flagged", "label": "Safety flagged", "multiplier": -1.0,
     "description": "PPE or ladder protocol not followed. Zeroes the entry."},
]

POINT_MODIFIERS_BY_CODE = {m["code"]: m for m in POINT_MODIFIERS}

SAFETY_MODIFIER = "safety_flagged"
WEATHER_MODIFIER = "adverse_weather"


def calculate_points(job_type, modifiers):
    """Points for one logged job. The single source of truth.

    Each modifier's delta is computed off the BASE points and added, so the
    preview can show one line per modifier. `safety_flagged` overrides
    everything and returns 0.

    The browser mirrors this from JOB_TYPES/POINT_MODIFIERS handed over as
    JSON, so nothing is hardcoded twice. floor(x + 0.5) is used rather than
    round() because Python rounds halves to even while JS Math.round goes
    half-up — that difference would silently drift the two apart.
    """
    job = JOB_TYPES_BY_CODE.get(job_type)
    if job is None:
        return 0
    modifiers = modifiers or []
    if SAFETY_MODIFIER in modifiers:
        return 0

    base = job["base_points"]
    total = base
    for code in modifiers:
        modifier = POINT_MODIFIERS_BY_CODE.get(code)
        if modifier:
            total += math.floor(base * modifier["multiplier"] + 0.5)
    return max(total, 0)


# Demo conversion rate only. Real rates vary by program, region and tier —
# this single number stands in for that whole table.
POINT_VALUE_USD = 0.18

NEXT_PAYOUT_DATE = "September 1, 2026"


def points_to_usd(points):
    """Dollar value of a point total at the demo rate."""
    return round(points * POINT_VALUE_USD, 2)



# ---------------------------------------------------------------------------
# Manager workspace reference data
# ---------------------------------------------------------------------------
# Team totals for the previous month, so KPI deltas are derived rather than
# invented at render time.
TEAM_PREVIOUS = {
    "points": 39_200,
    "repeat_rate": 9.4,
    "on_time_rate": 86.1,
    "jobs_this_week": 168,
    "csat": 4.05,
}

# 12 weeks of team totals for the trend chart.
TEAM_WEEKLY_POINTS = [
    3120, 3380, 2960, 3540, 3810, 3290,
    3670, 3950, 3420, 3780, 4090, 3860,
]

# Burnout thresholds — stated here so the UI can explain itself accurately.
BURNOUT_OVERTIME_HOURS = 10
BURNOUT_CONSECUTIVE_DAYS = 3
BURNOUT_REPEAT_RATE_MARGIN = 8

SUCCESS_METRICS = [
    {"code": "reduce_repeat", "label": "Reduce repeat rate", "unit": "%"},
    {"code": "increase_attach", "label": "Increase premium attach", "unit": "%"},
    {"code": "improve_on_time", "label": "Improve on-time arrival", "unit": "%"},
    {"code": "raise_csat", "label": "Raise CSAT", "unit": "/ 5"},
]

SUCCESS_METRICS_BY_CODE = {m["code"]: m for m in SUCCESS_METRICS}

PROGRAM_SCOPES = [
    {"code": "team", "label": "My team"},
    {"code": "region", "label": "Whole region"},
]


def agent_weekly_points(agent, weeks=8):
    """A deterministic 8-week series for one agent, derived from their totals.

    Not stored data — the shape is generated from the agent's own id and point
    total so every view shows the same series without another seed table.
    """
    average = max(agent["points"] // max(weeks, 1), 1)
    spread = [-18, 9, -6, 14, 22, -11, 5, 17]
    return [
        max(int(average * (100 + spread[(agent["id"] + i) % len(spread)]) / 100), 0)
        for i in range(weeks)
    ]


# ---------------------------------------------------------------------------
# Director workspace reference data
# ---------------------------------------------------------------------------
# These drive MODELLED estimates only — never measured results. Each is a
# stand-in assumption plugged into a simple multiplication so the director's
# ROI view has a number to show, not a figure pulled from a finance system.
ROI_ASSUMPTIONS = {
    "cost_per_truck_roll": {
        "value": 165.0,
        "label": "Cost per truck roll",
        "source": "Demo assumption, not a measured figure.",
    },
    "cost_to_replace_technician": {
        "value": 28500.0,
        "label": "Cost to replace a technician",
        "source": "Demo assumption, not a measured figure.",
    },
    "loaded_hourly_rate": {
        "value": 62.0,
        "label": "Loaded hourly rate",
        "source": "Demo assumption, not a measured figure.",
    },
    "program_leverage": {
        "value": 3.2,
        "label": "Modelled benefit per $1 of program spend",
        "source": "Demo assumption: an assumed multiplier, not a measured return.",
    },
}

# Quarter-to-date MODELLED volumes — inputs to the ROI attribution lines, not
# counts pulled from a ticketing system.
ROI_MODEL = {
    "repeat_visits_avoided": 1180,
    "techs_retained": 9,
    "hours_saved": 4200,
}

TERRITORY = {
    "nps": 41, "nps_prev": 37,
    "retention_rate": 88.5, "retention_prev": 85.2,
    "efficiency": 91.4, "efficiency_prev": 89.1,
    "repeat_rate": 8.9, "repeat_prev": 9.8,
    "quarterly_budget": 2100000,
    "technicians": 142,
    "managers": 6,
    "name": "Great Lakes Territory",
    "quarter": "Q3 2026",
}

# 12 weeks of territory totals for the trend chart. Points trend gently up
# while repeat rate trends gently down (fewer repeats = improving), so the
# two lines read as inversely correlated.
TERRITORY_WEEKLY = {
    "points": [18400, 18900, 19300, 19800, 20200, 20700,
               21300, 21900, 22600, 23200, 23900, 24600],
    "repeat_rate": [10.1, 9.9, 9.8, 9.6, 9.5, 9.3,
                    9.1, 9.0, 8.8, 8.7, 8.5, 8.4],
}

# Rollups for the five managers who are not the demo login. Marcus Vale (884)
# is deliberately absent — his numbers are computed live from his real 18
# technicians in LEADERBOARD, never stood up here.
MANAGER_TEAM_STATS = {
    885: {"points": 52300, "repeat_rate": 8.1, "on_time_rate": 90.2, "csat": 4.4, "overtime_hours": 38.5},
    886: {"points": 44100, "repeat_rate": 9.4, "on_time_rate": 87.6, "csat": 4.2, "overtime_hours": 52.0},
    887: {"points": 61800, "repeat_rate": 7.6, "on_time_rate": 92.8, "csat": 4.6, "overtime_hours": 29.0},
    888: {"points": 58900, "repeat_rate": 8.8, "on_time_rate": 89.1, "csat": 4.3, "overtime_hours": 46.5},
    889: {"points": 55200, "repeat_rate": 9.0, "on_time_rate": 88.4, "csat": 4.1, "overtime_hours": 41.0},
}


# ---------------------------------------------------------------------------
# Notification preferences, keyed by role so the template loops one list.
# ---------------------------------------------------------------------------
_BASE_PREF_GROUPS = [
    {
        "title": "Performance",
        "items": [
            {"key": "points_awarded", "label": "Points awarded",
             "description": "Every time a job clears review and posts to your balance.",
             "email": True, "push": True},
            {"key": "tier_promotion", "label": "Tier promotion",
             "description": "When you cross into a new tier.",
             "email": True, "push": True},
            {"key": "weekly_summary", "label": "Weekly summary",
             "description": "Your points and rank for the week, sent Monday morning.",
             "email": True, "push": False},
        ],
    },
    {
        "title": "Leaderboard",
        "items": [
            {"key": "rank_change", "label": "Rank change",
             "description": "When your position on the board moves.",
             "email": False, "push": True},
            {"key": "passed_by_agent", "label": "Someone passes you",
             "description": "When another agent overtakes your rank.",
             "email": False, "push": True},
            {"key": "monthly_reset", "label": "Monthly reset",
             "description": "When the board rolls over to a new month.",
             "email": True, "push": False},
        ],
    },
    {
        "title": "Program",
        "items": [
            {"key": "new_incentive", "label": "New incentive launched",
             "description": "Limited-time bonuses and seasonal multipliers.",
             "email": True, "push": True},
            {"key": "payout_processed", "label": "Payout processed",
             "description": "When a monthly payout leaves the queue.",
             "email": True, "push": False},
            {"key": "policy_updates", "label": "Policy updates",
             "description": "Changes to how points, tiers or payouts work.",
             "email": True, "push": False},
        ],
    },
]

_APPROVALS_GROUP = {
    "title": "Approvals",
    "items": [
        {"key": "log_submitted", "label": "Work log submitted",
         "description": "When one of your technicians files a log for approval.",
         "email": True, "push": True},
        {"key": "overtime_threshold", "label": "Overtime threshold breached",
         "description": "When a technician passes the weekly overtime ceiling.",
         "email": True, "push": True},
        {"key": "burnout_alert", "label": "Burnout alert",
         "description": "Sustained overtime paired with a falling CSAT score.",
         "email": True, "push": True},
    ],
}

_PROGRAMS_GROUP = {
    "title": "Programs",
    "items": [
        {"key": "program_submitted", "label": "Program submitted for approval",
         "description": "When a manager sends an incentive program up for sign-off.",
         "email": True, "push": True},
        {"key": "budget_threshold", "label": "Budget threshold",
         "description": "When committed spend crosses a share of the annual budget.",
         "email": True, "push": False},
        {"key": "quarterly_roi", "label": "Quarterly ROI ready",
         "description": "When the quarterly program return analysis is published.",
         "email": True, "push": False},
    ],
}

NOTIFICATION_PREFS = {
    ROLE_AGENT: _BASE_PREF_GROUPS,
    ROLE_MANAGER: _BASE_PREF_GROUPS + [_APPROVALS_GROUP],
    ROLE_DIRECTOR: _BASE_PREF_GROUPS + [_PROGRAMS_GROUP],
}

DIGEST_CHOICES = ["Daily", "Weekly", "Off"]
DIGEST_DEFAULT = "Weekly"
MUTE_ALL_DEFAULT = False


# ---------------------------------------------------------------------------
# Convenience lookups
# ---------------------------------------------------------------------------
def get_agent(agent_id):
    """Return a leaderboard agent by id, or None."""
    return next((a for a in LEADERBOARD if a["id"] == agent_id), None)


def reports_for_manager(manager_id):
    """Every technician reporting to a manager, ordered by rank."""
    return [a for a in LEADERBOARD if a["manager_id"] == manager_id]


if __name__ == "__main__":
    assert get_tier(0)["slug"] == "bronze"
    assert get_tier(2499)["slug"] == "bronze"
    assert get_tier(2500)["slug"] == "silver"
    assert get_tier(4999)["slug"] == "silver"
    assert get_tier(5000)["slug"] == "gold"
    assert points_to_next_tier(5000) is None
    assert points_to_next_tier(0) == ("Silver", 2500, 0)
    assert points_to_next_tier(CURRENT_AGENT["points"]) == ("Gold", 1820, 27)

    # Leaderboard shape
    assert len(LEADERBOARD) == 18
    assert [a["rank"] for a in LEADERBOARD] == list(range(1, 19))
    points = [a["points"] for a in LEADERBOARD]
    assert points == sorted(points, reverse=True), "ranks must follow points"
    assert {get_tier(a["points"])["slug"] for a in LEADERBOARD} == {"bronze", "silver", "gold"}
    assert get_agent(417)["rank"] == 4, "Dana stays rank 4 on her team"
    # The profile and the leaderboard row are two views of the same agent; if
    # they drift, the dashboard and the insight engine disagree.
    assert get_agent(AGENT_PROFILE["id"])["points"] == AGENT_PROFILE["points"]
    assert get_agent(AGENT_PROFILE["id"])["rank"] == AGENT_PROFILE["rank"]
    assert len(reports_for_manager(884)) == 18 == MANAGER_PROFILE["team_size"]

    # Roles and accounts
    assert set(DEMO_ACCOUNTS) == {
        "agent@spectrum.com", "manager@spectrum.com", "director@spectrum.com"}
    for email, account in DEMO_ACCOUNTS.items():
        assert account["profile"]["email"] == email
        assert account["role"] in ROLE_LABELS
        assert account["role"] in ROLE_HOME
    assert AGENT_PROFILE["manager_id"] == MANAGER_PROFILE["id"]
    assert MANAGER_PROFILE["manager_id"] == DIRECTOR_PROFILE["id"]
    assert any(m["id"] == MANAGER_PROFILE["id"] for m in ORG["managers"])
    assert len(ORG["managers"]) == DIRECTOR_PROFILE["managers_count"]

    # Notification prefs per role have unique keys
    for role, groups in NOTIFICATION_PREFS.items():
        keys = [i["key"] for g in groups for i in g["items"]]
        assert len(keys) == len(set(keys)), role
    assert len(NOTIFICATION_PREFS[ROLE_AGENT]) == 3
    assert len(NOTIFICATION_PREFS[ROLE_MANAGER]) == 4
    assert len(NOTIFICATION_PREFS[ROLE_DIRECTOR]) == 4
    assert DIGEST_DEFAULT in DIGEST_CHOICES

    # Work logging
    assert len(JOB_TYPES) == 9
    assert {j["group"] for j in JOB_TYPES} == set(JOB_TYPE_GROUPS)
    assert len(POINT_MODIFIERS) == 5
    # Base with no modifiers
    assert calculate_points("new_install_residential", []) == 120
    assert calculate_points("new_install_commercial", []) == 180
    # Additive deltas off the base
    assert calculate_points("new_install_residential", ["first_time_fix"]) == 138
    assert calculate_points("new_install_residential", ["premium_upsell"]) == 150
    assert calculate_points("new_install_residential", ["first_time_fix", "premium_upsell"]) == 168
    assert calculate_points("service_repair", ["after_hours"]) == 96
    # Half-value rounding must go half-up, matching JS Math.round
    assert math.floor(90 * 0.15 + 0.5) == 14
    assert calculate_points("signal_troubleshoot", ["first_time_fix"]) == 104
    # safety_flagged zeroes everything, whatever else is applied
    assert calculate_points("new_install_commercial", ["safety_flagged"]) == 0
    assert calculate_points("new_install_commercial",
                            ["first_time_fix", "premium_upsell", "safety_flagged"]) == 0
    assert calculate_points("nonsense", []) == 0
    assert calculate_points("service_repair", ["nonsense"]) == 80
    assert calculate_points("service_repair", None) == 80
    # Manager reference data
    assert len(TEAM_WEEKLY_POINTS) == 12
    assert len(SUCCESS_METRICS) == 4
    series = agent_weekly_points(get_agent(417))
    assert len(series) == 8 and all(p > 0 for p in series)
    assert agent_weekly_points(get_agent(417)) == series, "deterministic"

    # Ledger
    assert points_to_usd(1000) == 180.0
    assert POINT_VALUE_USD == 0.18

    # Director workspace reference data
    assert set(ROI_ASSUMPTIONS) == {
        "cost_per_truck_roll", "cost_to_replace_technician",
        "loaded_hourly_rate", "program_leverage"}
    for key, assumption in ROI_ASSUMPTIONS.items():
        assert "demo" in assumption["source"].lower(), key
        assert isinstance(assumption["value"], float), key
    assert ROI_ASSUMPTIONS["program_leverage"]["value"] == 3.2

    assert set(ROI_MODEL) == {"repeat_visits_avoided", "techs_retained", "hours_saved"}

    assert TERRITORY["name"] == "Great Lakes Territory"
    assert TERRITORY["managers"] == len(ORG["managers"])
    assert TERRITORY["technicians"] == DIRECTOR_PROFILE["technicians_count"]

    assert len(TERRITORY_WEEKLY["points"]) == 12
    assert len(TERRITORY_WEEKLY["repeat_rate"]) == 12
    assert all(18000 <= p <= 26000 for p in TERRITORY_WEEKLY["points"])
    assert all(8.4 <= r <= 10.2 for r in TERRITORY_WEEKLY["repeat_rate"])
    assert TERRITORY_WEEKLY["points"][-1] > TERRITORY_WEEKLY["points"][0], "points trend up"
    assert TERRITORY_WEEKLY["repeat_rate"][-1] < TERRITORY_WEEKLY["repeat_rate"][0], \
        "repeat rate trends down (improving)"

    assert 884 not in MANAGER_TEAM_STATS, "Marcus's numbers are computed live"
    assert set(MANAGER_TEAM_STATS) == {
        m["id"] for m in ORG["managers"] if not m["is_demo_user"]}
    for manager_id, stats in MANAGER_TEAM_STATS.items():
        assert set(stats) == {"points", "repeat_rate", "on_time_rate", "csat", "overtime_hours"}, manager_id

    print("mock_data OK")
