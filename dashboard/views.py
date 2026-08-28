from django.shortcuts import render

from . import mock_data


def landing(request):
    """Marketing landing page. All figures come from mock_data."""
    agent = mock_data.CURRENT_AGENT
    progress = mock_data.points_to_next_tier(agent["points"])
    return render(
        request,
        "dashboard/landing.html",
        {
            "tiers": mock_data.TIERS,
            "agent": agent,
            "agent_tier": mock_data.get_tier(agent["points"]),
            # None at the top tier — the template guards on it.
            "next_tier": (
                {"name": progress[0], "needed": progress[1], "percent": progress[2]}
                if progress
                else None
            ),
            "leaderboard": mock_data.LEADERBOARD,
            "kpi_stats": mock_data.KPI_STATS,
            "weekly_points": mock_data.WEEKLY_POINTS,
            "headline_stat": mock_data.HEADLINE_STAT,
        },
    )
