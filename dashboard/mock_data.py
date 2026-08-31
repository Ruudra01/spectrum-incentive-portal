"""Static reference data for the portal.

Holds what does NOT change at runtime: tiers and thresholds, KPI definitions,
the org chart, demo accounts, notification defaults, and the seed work-log
history. Anything mutable — live logs, programs, approvals — lives in store.py.

────────────────────────────────────────────────────────────────────────────
HOW THE NUMBERS FIT TOGETHER — read this before editing any figure.

SEEDED GROUND TRUTH (typed by hand, the only real inputs):
  * TIERS thresholds, JOB_TYPES base points, POINT_MODIFIERS, POINT_VALUE_USD
  * ARCHETYPES and each agent's archetype assignment
  * SEED_WORK_LOGS — entry-level history, generated deterministically
  * prior-period figures (KPI_PREVIOUS, TEAM_PREVIOUS) so a delta has
    something real to be a delta OF

DERIVED AT IMPORT (never typed twice, so nothing can drift):
  * Dana's points balance   = sum of her APPROVED entry points
  * every agent's points    = derived (Dana) or archetype monthly_points
  * rank                    = position after sorting by points
  * tier                    = get_tier(points)
  * WEEKLY_POINTS           = Dana's approved entries bucketed by week
  * points_this_week        = Dana's approved entries in the current week
  * team / territory totals = sums over their members
  * program budgets         = participants x bonus points x POINT_VALUE_USD

TWO LEVELS OF TRUTH, deliberately:
  Dana (417) plus the five agents whose logs the manager queue needs
  (803, 521, 288, 731, 540) carry ENTRY-LEVEL history — every point traces to
  a logged job. The other twelve carry AGGREGATE-ONLY monthly_points from
  their archetype, because seeding hundreds of entries for agents nobody
  drills into would be noise. Everything upward derives from that one number.

ARCHETYPES: the roster is generated from five recognisable kinds of
technician rather than random numbers, so the metrics correlate the way real
field-service metrics do — rushing causes callbacks, tenure builds skill.
See ARCHETYPES below.
────────────────────────────────────────────────────────────────────────────
"""

import itertools
import math
import random
from datetime import date, timedelta

# Work-log lifecycle. store.py aliases these; defined here because the seed
# history below needs them.
STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CHANGES = "changes_requested"

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
    # Prior month, so the team KPI deltas have a real basis.
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
    "quarterly_budget": 6000,      # incentive spend only, not the 8.4M dept budget
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
    # Performance is filled in below, DERIVED from her logged entries.
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
# The roster: five archetypes, not random numbers.
#
# Real field-service metrics correlate. Rushing causes callbacks, so high jobs
# + high overtime pulls CSAT down and repeat rate up. Tenure builds skill, so
# short-tenure agents sit lower on every measure. Generating from archetypes
# is what makes these read as people rather than a number table.
# ---------------------------------------------------------------------------
ARCHETYPES = {
    "veteran": {
        "label": "Veteran high performer",
        "monthly_points": (5600, 6500), "repeat_rate": (3.0, 4.4),
        "on_time_rate": (95.5, 97.8), "csat": (4.7, 4.9),
        "jobs": (12, 14), "overtime": (1.5, 4.0),
        "tenure": (52, 78), "safety": (6, 6),
    },
    "steady": {
        "label": "Steady mid-tier",
        "monthly_points": (2600, 4400), "repeat_rate": (5.0, 7.2),
        "on_time_rate": (90.0, 93.5), "csat": (4.3, 4.6),
        "jobs": (9, 11), "overtime": (4.0, 8.0),
        "tenure": (24, 46), "safety": (4, 5),
    },
    "fast_sloppy": {
        "label": "Fast but sloppy",
        # High volume, high overtime — and it shows in callbacks and CSAT.
        "monthly_points": (1700, 2400), "repeat_rate": (9.2, 11.5),
        "on_time_rate": (85.0, 88.5), "csat": (3.7, 4.0),
        # High hours, but deliberately kept under BURNOUT_OVERTIME_HOURS so the
        # burnout watch flags the burnout archetype and nobody else.
        "jobs": (12, 14), "overtime": (7.5, 9.6),
        "tenure": (14, 30), "safety": (3, 4),
    },
    "new_hire": {
        "label": "New hire ramping",
        # Under six months: fewer points, lower tier, more callbacks, fewer
        # audits passed — simply not enough time yet.
        "monthly_points": (700, 1500), "repeat_rate": (10.5, 13.6),
        "on_time_rate": (79.5, 84.0), "csat": (3.4, 3.8),
        "jobs": (6, 8), "overtime": (2.0, 5.5),
        "tenure": (2, 5), "safety": (1, 2),
    },
    "burnout_risk": {
        "label": "Burnout risk",
        # The only archetype above the 12hr overtime line — these are exactly
        # the agents the burnout watch is built to surface.
        "monthly_points": (1800, 2500), "repeat_rate": (8.8, 9.8),
        "on_time_rate": (86.0, 88.0), "csat": (3.8, 3.9),
        "jobs": (11, 13), "overtime": (13.5, 15.5),
        "tenure": (18, 27), "safety": (3, 3),
    },
}

# id, name, archetype. Dana (417) is "steady"; her points come from her own
# logged entries rather than the archetype range.
_ROSTER_PLAN = [
    (902, "Marcus Bell", "veteran"),
    (655, "Priya Raman", "veteran"),
    (731, "Alonzo Reyes", "steady"),
    (417, "Dana Whitfield", "steady"),
    (288, "Grace Okonkwo", "steady"),
    (540, "Tomas Lindqvist", "steady"),
    (119, "Renee Baptiste", "steady"),
    (803, "Ibrahim Cole", "burnout_risk"),
    (366, "Hana Fujimoto", "steady"),
    (474, "Wesley Adjei", "fast_sloppy"),
    (521, "Sofia Marchetti", "burnout_risk"),
    (638, "Darnell Pruitt", "fast_sloppy"),
    (712, "Aisha Nwosu", "fast_sloppy"),
    (845, "Victor Salazar", "burnout_risk"),
    (957, "Mei-Ling Chow", "new_hire"),
    (163, "Owen Brady", "new_hire"),
    (279, "Tasha Greenwood", "new_hire"),
    (384, "Rafael Ortiz", "new_hire"),
]

# Agents whose points trace to individual logged entries. Everyone else
# carries archetype aggregates only — stated plainly so it is not a mystery.
ENTRY_LEVEL_AGENTS = (417, 803, 521, 288, 731, 540)


def _spread(rng, low, high, decimals=1):
    value = rng.uniform(low, high)
    return round(value, decimals) if decimals else int(round(value))


def _build_roster():
    """Generate the 18 technicians from their archetypes, deterministically."""
    rng = random.Random(4172026)
    rows = []
    for agent_id, name, archetype in _ROSTER_PLAN:
        spec = ARCHETYPES[archetype]
        rows.append({
            "id": agent_id, "name": name, "archetype": archetype,
            "region": "Ohio Valley", "team": "Columbus North", "manager_id": 884,
            "monthly_points": _spread(rng, *spec["monthly_points"], decimals=0),
            "repeat_rate": _spread(rng, *spec["repeat_rate"]),
            "on_time_rate": _spread(rng, *spec["on_time_rate"]),
            "csat": _spread(rng, *spec["csat"], decimals=2),
            "jobs_this_week": _spread(rng, *spec["jobs"], decimals=0),
            "overtime_hours_this_week": _spread(rng, *spec["overtime"]),
            "tenure_months": _spread(rng, *spec["tenure"], decimals=0),
            "safety_audits_passed": _spread(rng, *spec["safety"], decimals=0),
        })
    return rows


_ROSTER = _build_roster()


# ---------------------------------------------------------------------------
# Seed work-log history. Entry-level truth for the six agents above.
# ---------------------------------------------------------------------------
_JOB_MIX = [
    "new_install_residential", "new_install_residential", "service_repair",
    "signal_troubleshoot", "equipment_swap", "upgrade_premium_router",
    "new_install_commercial", "aerial_line_work", "underground_drop",
    "customer_education",
]

_STREETS = [
    "1420 Neil Ave, Columbus", "88 Grandview Ave, Columbus",
    "3307 Indianola Ave, Columbus", "615 Parsons Ave, Columbus",
    "2210 Henderson Rd, Columbus", "47 Hudson St, Columbus",
    "1902 Olentangy River Rd, Columbus", "760 Kenny Rd, Columbus",
    "5140 Sinclair Rd, Columbus", "231 Chittenden Ave, Columbus",
]


def _entry(counter, agent_id, agent_name, on_date, job_type, modifiers, minutes,
           street, status, ref_n, review_note=""):
    decided = status in (STATUS_APPROVED, STATUS_REJECTED, STATUS_CHANGES)
    submitted = status != STATUS_DRAFT
    return {
        "id": next(counter), "agent_id": agent_id, "agent_name": agent_name,
        "manager_id": 884, "date": on_date.isoformat(), "job_type": job_type,
        "work_order_ref": f"WO-2026-{ref_n:04d}", "address_line": street,
        "duration_minutes": minutes, "modifiers": list(modifiers),
        "notes": "",
        "points": calculate_points(job_type, modifiers),
        "status": status,
        "submitted_at": f"{on_date.isoformat()} 17:40" if submitted else None,
        "reviewed_at": f"{(on_date + timedelta(days=1)).isoformat()} 08:15" if decided else None,
        "reviewer_id": 884 if decided else None,
        "review_note": review_note,
    }


# Average points a job across the mix, used to size daily volume.
_AVG_JOB_POINTS = sum(JOB_TYPES_BY_CODE[c]["base_points"] for c in _JOB_MIX) / len(_JOB_MIX)
_WORKING_DAYS = 16          # weekdays in a ~3 week window


def _jobs_for_day(rng, archetype):
    """Daily job count implied by the archetype's monthly point target."""
    low, high = ARCHETYPES[archetype]["monthly_points"]
    target = (low + high) / 2
    per_day = target / _AVG_JOB_POINTS / _WORKING_DAYS
    whole = int(per_day)
    # Carry the fraction as a probability so the monthly total lands on target.
    return max(whole + (1 if rng.random() < per_day - whole else 0), 0)


def _build_seed_logs():
    """Three weeks of history, weighted to weekdays with occasional weekend work."""
    rng = random.Random(20260831)
    counter = itertools.count(1)
    today = date.today()
    logs = []
    ref = 100

    for agent_id in ENTRY_LEVEL_AGENTS:
        agent = next(a for a in _ROSTER if a["id"] == agent_id)
        is_dana = agent_id == 417
        for days_back in range(21, 0, -1):
            day = today - timedelta(days=days_back)
            weekend = day.weekday() >= 5
            # Predominantly weekdays; Saturday work is occasional, Sunday rare.
            if weekend and rng.random() > (0.18 if day.weekday() == 5 else 0.04):
                continue
            # Entry-level agents all work a comparable pattern, so a derived
            # balance lands in the same range as an archetype aggregate.
            if not is_dana and rng.random() < 0.12:
                continue

            # Volume comes FROM the archetype, so an entry-level balance lands
            # in the same range as an aggregate one for the same kind of agent.
            # It is also bounded by the tier scale: at ~125 points a job, 3-7
            # jobs/day would earn ~12,000 points a month and every agent would
            # clear Gold (5,000) within a week, making the tiers meaningless.
            jobs_today = _jobs_for_day(rng, agent["archetype"])
            for _ in range(jobs_today):
                ref += 1
                job = rng.choice(_JOB_MIX)
                minutes = JOB_TYPES_BY_CODE[job]["est_minutes"] + rng.choice(
                    [-15, -10, 0, 0, 10, 20, 30])
                modifiers = []
                if rng.random() < 0.45:
                    modifiers.append("first_time_fix")
                if rng.random() < 0.20:
                    modifiers.append("premium_upsell")
                if rng.random() < 0.12:
                    modifiers.append("after_hours")
                if rng.random() < 0.08:
                    modifiers.append("adverse_weather")

                status = STATUS_APPROVED
                if not is_dana and days_back <= 3 and rng.random() < 0.6:
                    status = STATUS_SUBMITTED
                logs.append(_entry(counter, agent_id, agent["name"], day, job,
                                   modifiers, minutes, rng.choice(_STREETS),
                                   status, ref))

    # Guarantee a review queue whatever weekday the demo runs on.
    for agent_id in ENTRY_LEVEL_AGENTS:
        if agent_id == 417:
            continue
        theirs = [l for l in logs if l["agent_id"] == agent_id]
        if not theirs or any(l["status"] == STATUS_SUBMITTED for l in theirs):
            continue
        latest = max(theirs, key=lambda l: l["date"])
        latest.update(status=STATUS_SUBMITTED, reviewed_at=None, reviewer_id=None)

    # Dana's review outcomes, dated recently enough to still be actionable.
    ref += 1
    logs.append(_entry(counter, 417, "Dana Whitfield", today - timedelta(days=5),
                       "equipment_swap", [], 35, "47 Hudson St, Columbus",
                       STATUS_REJECTED, ref,
                       "Work order WO-2026-0091 already covers this swap."))
    ref += 1
    logs.append(_entry(counter, 417, "Dana Whitfield", today - timedelta(days=3),
                       "aerial_line_work", ["after_hours"], 145,
                       "5140 Sinclair Rd, Columbus", STATUS_REJECTED, ref,
                       "After-hours flag needs dispatch approval on file."))
    ref += 1
    logs.append(_entry(counter, 417, "Dana Whitfield", today - timedelta(days=2),
                       "new_install_commercial", ["premium_upsell"], 165,
                       "760 Kenny Rd, Columbus", STATUS_CHANGES, ref,
                       "Add the suite number to the work order and resubmit."))

    # Two drafts from today, ready to submit.
    for job, mods, minutes, street in (
        ("new_install_residential", ["first_time_fix"], 85, "1420 Neil Ave, Columbus"),
        ("signal_troubleshoot", ["first_time_fix", "adverse_weather"], 80,
         "3307 Indianola Ave, Columbus"),
    ):
        ref += 1
        logs.append(_entry(counter, 417, "Dana Whitfield", today, job, mods,
                           minutes, street, STATUS_DRAFT, ref))
    return logs


SEED_WORK_LOGS = _build_seed_logs()


# ---------------------------------------------------------------------------
# DERIVED: every figure below is computed, never typed.
# ---------------------------------------------------------------------------
def _approved_for(agent_id):
    return [l for l in SEED_WORK_LOGS
            if l["agent_id"] == agent_id and l["status"] == STATUS_APPROVED]


def _derived_points(agent_id):
    """Entry-level agents earn their balance; the rest carry archetype totals."""
    if agent_id in ENTRY_LEVEL_AGENTS:
        return sum(l["points"] for l in _approved_for(agent_id))
    return next(a["monthly_points"] for a in _ROSTER if a["id"] == agent_id)


def _build_leaderboard():
    rows = []
    for agent in _ROSTER:
        row = {k: v for k, v in agent.items() if k != "monthly_points"}
        row["points"] = _derived_points(agent["id"])
        rows.append(row)
    rows.sort(key=lambda a: -a["points"])
    for position, row in enumerate(rows, start=1):
        row["rank"] = position          # rank IS the sorted position
    return rows


LEADERBOARD = _build_leaderboard()


def _weekly_points(agent_id, weeks=8):
    """Approved entries bucketed into the last `weeks` calendar weeks."""
    today = date.today()
    buckets = [0] * weeks
    for entry in _approved_for(agent_id):
        delta_weeks = (today - date.fromisoformat(entry["date"])).days // 7
        if 0 <= delta_weeks < weeks:
            buckets[weeks - 1 - delta_weeks] += entry["points"]
    return buckets


def _points_this_week(agent_id):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return sum(l["points"] for l in _approved_for(agent_id)
               if date.fromisoformat(l["date"]) >= monday)


# Dana's headline figures come straight off her own logged work.
_DANA = next(a for a in LEADERBOARD if a["id"] == AGENT_PROFILE["id"])
AGENT_PROFILE["points"] = _DANA["points"]
AGENT_PROFILE["rank"] = _DANA["rank"]
AGENT_PROFILE["points_this_week"] = _points_this_week(AGENT_PROFILE["id"])

# The sparkline is the same entries bucketed by week — not a parallel list.
WEEKLY_POINTS = _weekly_points(AGENT_PROFILE["id"])


MANAGER_PROFILE["direct_report_ids"] = [a["id"] for a in LEADERBOARD]

# ---------------------------------------------------------------------------
# Agent dashboard figures
# ---------------------------------------------------------------------------
# Prior-period ground truth. A delta must be a delta OF something.
KPI_PREVIOUS = {
    # Last month's actuals, on the same scale as the derived current figures.
    "installs": 6,
    "upsell_conversion": 17.8,
    "points_this_week": 0,      # filled below from last week's real entries
}


def _points_last_week(agent_id):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    prior = monday - timedelta(days=7)
    return sum(l["points"] for l in _approved_for(agent_id)
               if prior <= date.fromisoformat(l["date"]) < monday)


KPI_PREVIOUS["points_this_week"] = _points_last_week(AGENT_PROFILE["id"])

# Installs this month = Dana's approved install jobs this calendar month.
_INSTALL_CODES = ("new_install_residential", "new_install_commercial")
_INSTALLS_THIS_MONTH = sum(
    1 for l in _approved_for(AGENT_PROFILE["id"])
    if l["job_type"] in _INSTALL_CODES
    and date.fromisoformat(l["date"]).month == date.today().month
)
# Upsell conversion = share of approved jobs carrying the premium modifier.
_APPROVED = _approved_for(AGENT_PROFILE["id"])
_UPSELL_RATE = round(
    100 * sum(1 for l in _APPROVED if "premium_upsell" in l["modifiers"]) / max(len(_APPROVED), 1), 1)


def _delta(now, before):
    """Percent change, or 0 when there is no prior figure to compare against."""
    return round((now - before) / before * 100, 1) if before else 0.0


# The fourth dashboard tile is "Earned today", computed live from
# store.get_day_summary rather than being a static figure here.
KPI_STATS = [
    {"label": "Installs this month", "value": _INSTALLS_THIS_MONTH, "unit": "",
     "delta": _delta(_INSTALLS_THIS_MONTH, KPI_PREVIOUS["installs"]),
     "direction": "up" if _INSTALLS_THIS_MONTH >= KPI_PREVIOUS["installs"] else "down"},
    {"label": "Upsell conversion", "value": _UPSELL_RATE, "unit": "%",
     "delta": _delta(_UPSELL_RATE, KPI_PREVIOUS["upsell_conversion"]),
     "direction": "up" if _UPSELL_RATE >= KPI_PREVIOUS["upsell_conversion"] else "down"},
    {"label": "Points this week", "value": AGENT_PROFILE["points_this_week"], "unit": "pts",
     "delta": _delta(AGENT_PROFILE["points_this_week"], KPI_PREVIOUS["points_this_week"]),
     "direction": "up" if AGENT_PROFILE["points_this_week"] >= KPI_PREVIOUS["points_this_week"] else "down"},
]


HEADLINE_STAT = {
    "label": "Points awarded to field agents this quarter",
    "value": sum(agent["points"] for agent in LEADERBOARD),
    "unit": "pts",
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
    # These assert RELATIONSHIPS, not magic numbers. If a figure is derived,
    # the test proves it still equals what it is derived from.
    assert get_tier(0)["slug"] == "bronze"
    assert get_tier(2499)["slug"] == "bronze"
    assert get_tier(2500)["slug"] == "silver"
    assert get_tier(4999)["slug"] == "silver"
    assert get_tier(5000)["slug"] == "gold"
    assert points_to_next_tier(5000) is None
    assert points_to_next_tier(0) == ("Silver", 2500, 0)

    # --- Points calculation ---
    assert calculate_points("new_install_residential", []) == 120
    assert calculate_points("new_install_residential", ["first_time_fix"]) == 138
    assert calculate_points("new_install_residential", ["first_time_fix", "premium_upsell"]) == 168
    assert calculate_points("new_install_commercial", ["safety_flagged"]) == 0
    assert calculate_points("nonsense", []) == 0
    assert math.floor(90 * 0.15 + 0.5) == 14      # half-up, matching JS
    assert points_to_usd(1000) == 180.0

    # --- Derivation: nothing is typed twice ---
    dana = AGENT_PROFILE["id"]
    assert AGENT_PROFILE["points"] == sum(l["points"] for l in _approved_for(dana)), \
        "balance must equal the sum of approved entries"
    assert AGENT_PROFILE["points_this_week"] == _points_this_week(dana)
    assert WEEKLY_POINTS == _weekly_points(dana)
    assert sum(WEEKLY_POINTS) <= AGENT_PROFILE["points"], \
        "an 8-week window cannot exceed the all-time balance"
    name, needed, _pct = points_to_next_tier(AGENT_PROFILE["points"])
    threshold = next(t["min_points"] for t in TIERS if t["name"] == name)
    assert needed == threshold - AGENT_PROFILE["points"]

    # --- Roster ---
    assert len(LEADERBOARD) == 18
    points = [a["points"] for a in LEADERBOARD]
    assert points == sorted(points, reverse=True), "rank order must follow points"
    assert [a["rank"] for a in LEADERBOARD] == list(range(1, 19))
    assert {get_tier(a["points"])["slug"] for a in LEADERBOARD} == {"bronze", "silver", "gold"}
    assert get_agent(dana)["points"] == AGENT_PROFILE["points"]
    assert get_agent(dana)["rank"] == AGENT_PROFILE["rank"]
    assert len(reports_for_manager(884)) == 18 == MANAGER_PROFILE["team_size"]

    # --- Archetypes describe plausible people ---
    burnout = [a for a in LEADERBOARD if a["archetype"] == "burnout_risk"]
    assert 2 <= len(burnout) <= 3, f"burnout risks should be rare, got {len(burnout)}"
    over = [a for a in LEADERBOARD
            if a["overtime_hours_this_week"] > BURNOUT_OVERTIME_HOURS]
    assert {a["id"] for a in over} == {a["id"] for a in burnout}, \
        "the burnout watch must flag the burnout archetype and nobody else"
    for agent in LEADERBOARD:
        if get_tier(agent["points"])["slug"] == "gold":
            assert agent["repeat_rate"] < 5.0, f"{agent['name']}: gold with a high repeat rate"
        if agent["tenure_months"] < 6:
            assert get_tier(agent["points"])["slug"] == "bronze", \
                f"{agent['name']}: too new to be above bronze"
            assert agent["safety_audits_passed"] <= 2
    # on-time and CSAT move together
    by_on_time = sorted(LEADERBOARD, key=lambda a: a["on_time_rate"])
    assert by_on_time[0]["csat"] < by_on_time[-1]["csat"]

    # --- Dates are sane relative to today ---
    today = date.today()
    assert all(l["date"] <= today.isoformat() for l in SEED_WORK_LOGS), "no future entries"
    dana_days = {l["date"] for l in SEED_WORK_LOGS if l["agent_id"] == dana}
    weekend = sum(1 for d in dana_days if date.fromisoformat(d).weekday() >= 5)
    assert weekend / len(dana_days) < 0.3, "history should be predominantly weekdays"
    per_day = {}
    for l in SEED_WORK_LOGS:
        if l["agent_id"] == dana:
            per_day[l["date"]] = per_day.get(l["date"], 0) + 1
    assert len(set(per_day.values())) > 1, "daily job counts must vary"
    for status in (STATUS_REJECTED, STATUS_CHANGES):
        for l in SEED_WORK_LOGS:
            if l["agent_id"] == dana and l["status"] == status:
                age = (today - date.fromisoformat(l["date"])).days
                assert age <= 10, f"{status} entry is {age} days old — not actionable"

    # --- KPI deltas have a real prior value ---
    for kpi in KPI_STATS:
        assert kpi["direction"] in ("up", "down")
    assert KPI_PREVIOUS["points_this_week"] == _points_last_week(dana)

    # --- Roles and accounts ---
    assert set(DEMO_ACCOUNTS) == {
        "agent@spectrum.com", "manager@spectrum.com", "director@spectrum.com"}
    for email, account in DEMO_ACCOUNTS.items():
        assert account["profile"]["email"] == email
        assert account["role"] in ROLE_LABELS and account["role"] in ROLE_HOME
    assert AGENT_PROFILE["manager_id"] == MANAGER_PROFILE["id"]
    assert MANAGER_PROFILE["manager_id"] == DIRECTOR_PROFILE["id"]
    assert len(ORG["managers"]) == DIRECTOR_PROFILE["managers_count"]

    # --- Notification prefs ---
    for role, groups in NOTIFICATION_PREFS.items():
        keys = [i["key"] for g in groups for i in g["items"]]
        assert len(keys) == len(set(keys)), role
    assert DIGEST_DEFAULT in DIGEST_CHOICES

    # --- Manager reference data ---
    assert len(TERRITORY_WEEKLY["points"]) == 12
    assert len(SUCCESS_METRICS) == 4
    assert 884 not in MANAGER_TEAM_STATS, "Marcus is computed from real agents"

    print("mock_data OK")
