from django.shortcuts import render

from . import mock_data


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
        },
    )
