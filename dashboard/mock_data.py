"""Single source of truth for every point value and threshold in the portal.

Shaped like a JSON API response: plain dicts and lists only, so each constant
can be swapped for a real endpoint payload without touching a template.
"""

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

CURRENT_AGENT = {
    "id": 417,
    "name": "Dana Whitfield",
    "employee_id": "SPC-0417",
    "region": "Central Ohio",
    "team": "Residential Install",
    "initials": "DW",
    "points": 3180,
    "rank": 4,
    "points_this_week": 240,
}

LEADERBOARD = [
    {"id": 902, "name": "Marcus Bell", "region": "West Michigan", "points": 6400, "rank": 1},
    {"id": 655, "name": "Priya Raman", "region": "North Texas", "points": 5720, "rank": 2},
    {"id": 731, "name": "Alonzo Reyes", "region": "Central Ohio", "points": 4310, "rank": 3},
    {"id": 417, "name": "Dana Whitfield", "region": "Central Ohio", "points": 3180, "rank": 4},
    {"id": 288, "name": "Grace Okonkwo", "region": "Upstate New York", "points": 2960, "rank": 5},
    {"id": 540, "name": "Tomas Lindqvist", "region": "North Texas", "points": 2740, "rank": 6},
    {"id": 119, "name": "Renee Baptiste", "region": "South Florida", "points": 2510, "rank": 7},
    {"id": 803, "name": "Ibrahim Cole", "region": "West Michigan", "points": 2280, "rank": 8},
    {"id": 366, "name": "Hana Fujimoto", "region": "South Florida", "points": 2080, "rank": 9},
    {"id": 474, "name": "Wesley Adjei", "region": "Upstate New York", "points": 1900, "rank": 10},
]

KPI_STATS = [
    {"label": "Installs this month", "value": 38, "unit": "", "delta": 12.5, "direction": "up"},
    {"label": "Upsell conversion", "value": 24.8, "unit": "%", "delta": 3.1, "direction": "up"},
    {"label": "CSAT", "value": 4.6, "unit": "/ 5", "delta": 0.2, "direction": "down"},
    {"label": "Points this week", "value": 240, "unit": "pts", "delta": 18.0, "direction": "up"},
]

WEEKLY_POINTS = [180, 205, 160, 240, 275, 210, 255, 240]

# ---------------------------------------------------------------------------
# DEMO CREDENTIALS — frontend prototype only.
# These are hardcoded on purpose so a reviewer can sign in without a database.
# Replace with a real auth backend (hashed passwords, a user store, rate
# limiting) before any non-demo use. Do not deploy this as-is.
# ---------------------------------------------------------------------------
DEMO_EMAIL = "agent@spectrum.com"
DEMO_PASSWORD = "spectrum2026"

# Profile page fields, layered on top of CURRENT_AGENT so identity stays in
# one place. phone and location are the only editable values.
PROFILE_DATA = dict(
    CURRENT_AGENT,
    email=DEMO_EMAIL,
    phone="(614) 555-0142",
    job_title="Field Installation Technician",
    manager_name="Lorraine Deckard",
    hire_date="March 4, 2023",
    location="Columbus, OH",
)

# Notification preferences. Each item's default channels seed a fresh session.
NOTIFICATION_PREFS = [
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

DIGEST_CHOICES = ["Daily", "Weekly", "Off"]
DIGEST_DEFAULT = "Weekly"
MUTE_ALL_DEFAULT = False

HEADLINE_STAT = {
    "label": "Points awarded to field agents this quarter",
    "value": sum(agent["points"] for agent in LEADERBOARD),
    "unit": "pts",
}


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


if __name__ == "__main__":
    assert get_tier(0)["slug"] == "bronze"
    assert get_tier(2499)["slug"] == "bronze"
    assert get_tier(2500)["slug"] == "silver"
    assert get_tier(4999)["slug"] == "silver"
    assert get_tier(5000)["slug"] == "gold"
    assert get_tier(99999)["slug"] == "gold"
    assert points_to_next_tier(5000) is None
    assert points_to_next_tier(0) == ("Silver", 2500, 0)
    assert points_to_next_tier(CURRENT_AGENT["points"]) == ("Gold", 1820, 27)
    assert [t["rank"] for t in LEADERBOARD] == list(range(1, 11))
    assert next(a for a in LEADERBOARD if a["id"] == CURRENT_AGENT["id"])["rank"] == 4
    assert {get_tier(a["points"])["slug"] for a in LEADERBOARD} == {"bronze", "silver", "gold"}
    assert PROFILE_DATA["employee_id"] == CURRENT_AGENT["employee_id"]
    assert PROFILE_DATA["email"] == DEMO_EMAIL
    keys = [i["key"] for g in NOTIFICATION_PREFS for i in g["items"]]
    assert len(keys) == len(set(keys)) == 9, keys
    assert DIGEST_DEFAULT in DIGEST_CHOICES
    print("mock_data OK")
