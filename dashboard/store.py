"""In-memory prototype store for state that CHANGES at runtime.

WARNING — this is process-global memory, not a database:
  * Every worker restart wipes it.
  * It does NOT survive multiple processes. Run a single dev worker, or two
    users will see two different worlds.
  * There is no durability, no transactions and no migration path.
Replace with real Django models before any non-demo use.

Session storage cannot carry a workflow between two people — when an agent
submits a work log, a manager in a different browser has to see it. That is
what this module is for. Static reference data stays in mock_data.py.

Views must never touch STORE directly; go through the helpers below, which
hold _LOCK for every mutation (the dev server is threaded).
"""

import copy
import itertools
import random
import threading
from datetime import date, datetime, timedelta

from . import mock_data

_LOCK = threading.Lock()

# Work-log lifecycle: draft -> submitted -> approved | rejected | changes_requested
# changes_requested returns an entry to editable while keeping the reviewer note.
STATUS_DRAFT = "draft"
STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CHANGES = "changes_requested"

EDITABLE_STATUSES = (STATUS_DRAFT, STATUS_CHANGES)

STATUS_LABELS = {
    STATUS_DRAFT: "Draft",
    STATUS_SUBMITTED: "Submitted",
    STATUS_APPROVED: "Approved",
    STATUS_REJECTED: "Rejected",
    STATUS_CHANGES: "Changes requested",
}

# Kept so older call sites reading a "pending" queue still resolve.
STATUS_PENDING = STATUS_SUBMITTED

PROGRAM_DRAFT = "draft"
PROGRAM_CHANGES = "changes_requested"
PROGRAM_PENDING = "pending"
PROGRAM_APPROVED = "approved"
PROGRAM_REJECTED = "rejected"



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

# The five reports besides Dana whose history seeds Marcus's queue and team views.
_SEEDED_AGENTS = [
    (417, "Dana Whitfield"),
    (803, "Ibrahim Cole"),
    (521, "Sofia Marchetti"),
    (288, "Grace Okonkwo"),
    (731, "Alonzo Reyes"),
    (540, "Tomas Lindqvist"),
]


def _entry(counter, agent_id, agent_name, on_date, job_type, modifiers, minutes,
           street, status, ref_n, review_note="", reviewer="Marcus Vale"):
    decided = status in (STATUS_APPROVED, STATUS_REJECTED, STATUS_CHANGES)
    submitted = status != STATUS_DRAFT
    return {
        "id": next(counter),
        "agent_id": agent_id,
        "agent_name": agent_name,
        "manager_id": 884,
        "date": on_date.isoformat(),
        "job_type": job_type,
        "work_order_ref": f"WO-2026-{ref_n:04d}",
        "address_line": street,
        "duration_minutes": minutes,
        "modifiers": list(modifiers),
        "notes": "",
        "points": mock_data.calculate_points(job_type, modifiers),
        "status": status,
        "submitted_at": f"{on_date.isoformat()} 17:40" if submitted else None,
        "reviewed_at": f"{(on_date + timedelta(days=1)).isoformat()} 08:15" if decided else None,
        "reviewer_id": 884 if decided else None,
        "review_note": review_note,
    }



def _program(pid, name, description, created_by, owner_name, team, status,
             start, end, job_types, rules, budget, participants,
             metric, target, scope="team", note="", reviewed_by=None, reviewed_at=None):
    return {
        "id": pid, "name": name, "description": description,
        "created_by": created_by, "owner_name": owner_name,
        "created_at": start, "status": status,
        "start_date": start, "end_date": end,
        "target_scope": scope, "target_team": team,
        "job_types": list(job_types),
        "bonus_structure": [dict(r) for r in rules],
        "budget_estimate": budget,
        "expected_participants": participants,
        "success_metric": metric, "success_target": target,
        "director_note": note, "reviewed_by": reviewed_by, "reviewed_at": reviewed_at,
    }


def _seed_programs():
    """Four programs across the statuses, so the director's Part 4 comparison
    view has real material to work with."""
    return [
        _program(1, "Q4 Upsell Accelerator",
                 "Double down on mobile line attachments through the Q4 push.",
                 884, "Marcus Vale", "Columbus North", PROGRAM_PENDING,
                 "2026-10-01", "2026-12-31",
                 ["new_install_residential", "upgrade_premium_router"],
                 [{"count": 5, "job_type": "new_install_residential", "bonus": 250}],
                 45000, 18, "increase_attach", 12),
        _program(2, "Safety Streak Bonus",
                 "Reward six consecutive clean safety audits.",
                 885, "Deirdre Kwan", "Cleveland East", PROGRAM_PENDING,
                 "2026-09-01", "2026-11-30",
                 ["aerial_line_work", "underground_drop"],
                 [{"count": 6, "job_type": "aerial_line_work", "bonus": 300}],
                 18000, 24, "improve_on_time", 4),
        _program(3, "Summer Install Sprint",
                 "Seasonal multiplier on completed residential installs.",
                 884, "Marcus Vale", "Columbus North", PROGRAM_APPROVED,
                 "2026-06-01", "2026-08-31",
                 ["new_install_residential", "new_install_commercial"],
                 [{"count": 10, "job_type": "new_install_residential", "bonus": 400}],
                 32000, 18, "reduce_repeat", 3,
                 note="Approved at full budget.",
                 reviewed_by="Priya Raghunathan", reviewed_at="2026-05-14 16:20"),
        _program(4, "Weekend Coverage Pilot",
                 "Premium points for Saturday appointment slots.",
                 886, "Hollis Barrera", "Toledo West", PROGRAM_REJECTED,
                 "2026-07-01", "2026-09-30",
                 ["service_repair", "signal_troubleshoot"],
                 [{"count": 4, "job_type": "service_repair", "bonus": 180}],
                 26000, 21, "raise_csat", 4,
                 note="Overlaps the install sprint; resubmit for Q1.",
                 reviewed_by="Priya Raghunathan", reviewed_at="2026-06-05 11:00"),
    ]


def _seed_work_logs():
    """About three weeks of history so every view has real content."""
    rng = random.Random(20260828)
    counter = itertools.count(1)
    today = date.today()
    logs = []
    ref = 100

    for agent_id, agent_name in _SEEDED_AGENTS:
        is_dana = agent_id == 417
        # Dana carries the richest history; the others seed the manager queue.
        for days_back in range(21, 0, -1):
            day = today - timedelta(days=days_back)
            if day.weekday() == 6:            # no Sunday work
                continue
            if not is_dana and rng.random() < 0.45:
                continue

            for _ in range(rng.randint(2, 4) if is_dana else rng.randint(1, 2)):
                ref += 1
                job = rng.choice(_JOB_MIX)
                base_minutes = mock_data.JOB_TYPES_BY_CODE[job]["est_minutes"]
                minutes = base_minutes + rng.choice([-15, -10, 0, 0, 10, 20, 30])
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
                note = ""
                # A few of the other agents leave work awaiting review.
                if not is_dana and days_back <= 3 and rng.random() < 0.7:
                    status = STATUS_SUBMITTED
                logs.append(_entry(counter, agent_id, agent_name, day, job,
                                   modifiers, minutes, rng.choice(_STREETS),
                                   status, ref, note))

    # Dana's specific review outcomes, so the UI shows every state.
    ref += 1
    logs.append(_entry(counter, 417, "Dana Whitfield", today - timedelta(days=12),
                       "equipment_swap", [], 35, "47 Hudson St, Columbus",
                       STATUS_REJECTED, ref,
                       "Work order WO-2026-0091 already covers this swap."))
    ref += 1
    logs.append(_entry(counter, 417, "Dana Whitfield", today - timedelta(days=6),
                       "aerial_line_work", ["after_hours"], 145,
                       "5140 Sinclair Rd, Columbus", STATUS_REJECTED, ref,
                       "After-hours flag needs dispatch approval on file."))
    ref += 1
    logs.append(_entry(counter, 417, "Dana Whitfield", today - timedelta(days=3),
                       "new_install_commercial", ["premium_upsell"], 165,
                       "760 Kenny Rd, Columbus", STATUS_CHANGES, ref,
                       "Add the suite number to the work order and resubmit."))

    # Two drafts from today, ready to submit.
    ref += 1
    logs.append(_entry(counter, 417, "Dana Whitfield", today,
                       "new_install_residential", ["first_time_fix"], 85,
                       "1420 Neil Ave, Columbus", STATUS_DRAFT, ref))
    ref += 1
    logs.append(_entry(counter, 417, "Dana Whitfield", today,
                       "signal_troubleshoot", ["first_time_fix", "adverse_weather"], 80,
                       "3307 Indianola Ave, Columbus", STATUS_DRAFT, ref))

    return logs


def _seed():
    """The state a fresh process (or a reset) starts from."""
    return {
        "work_logs": _seed_work_logs(),
        "programs": _seed_programs(),
        "notifications": [],
    }


def _stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


STORE = _seed()
_ids = {
    "work_logs": itertools.count(max(l["id"] for l in STORE["work_logs"]) + 1),
    "programs": itertools.count(max(p["id"] for p in STORE["programs"]) + 1),
    "notifications": itertools.count(1),
}


def reset_store():
    """Restore the seed state. Used by /dev/reset-store/ so a demo restarts clean."""
    global STORE
    with _LOCK:
        STORE = _seed()
        _ids["work_logs"] = itertools.count(max(l["id"] for l in STORE["work_logs"]) + 1)
        _ids["programs"] = itertools.count(max(p["id"] for p in STORE["programs"]) + 1)
        _ids["notifications"] = itertools.count(1)


# --- Work logs -------------------------------------------------------------
def get_entries_for_agent(agent_id, on_date=None):
    """An agent's entries, newest first. Optionally limited to one date."""
    with _LOCK:
        entries = [l for l in STORE["work_logs"] if l["agent_id"] == agent_id]
        if on_date:
            entries = [l for l in entries if l["date"] == on_date]
        entries.sort(key=lambda l: (l["date"], l["id"]), reverse=True)
        return copy.deepcopy(entries)


def get_entry(entry_id):
    with _LOCK:
        return copy.deepcopy(
            next((l for l in STORE["work_logs"] if l["id"] == entry_id), None))


def add_entry(agent_id, agent_name, manager_id, on_date, job_type, work_order_ref,
              address_line, duration_minutes, modifiers, notes="",
              status=STATUS_DRAFT):
    """Create an entry. Points are always recalculated here — a caller's
    number is never trusted."""
    with _LOCK:
        entry = {
            "id": next(_ids["work_logs"]),
            "agent_id": agent_id,
            "agent_name": agent_name,
            "manager_id": manager_id,
            "date": on_date,
            "job_type": job_type,
            "work_order_ref": work_order_ref,
            "address_line": address_line,
            "duration_minutes": duration_minutes,
            "modifiers": list(modifiers or []),
            "notes": notes,
            "points": mock_data.calculate_points(job_type, modifiers),
            "status": status,
            "submitted_at": _stamp() if status == STATUS_SUBMITTED else None,
            "reviewed_at": None,
            "reviewer_id": None,
            "review_note": "",
        }
        STORE["work_logs"].append(entry)
        return copy.deepcopy(entry)


def update_entry(entry_id, agent_id, **fields):
    """Edit an entry the agent owns, only while it is editable.

    Returns the updated copy, or None when the entry is missing, owned by
    someone else, or locked (submitted / approved / rejected).
    """
    allowed = {"job_type", "work_order_ref", "address_line",
               "duration_minutes", "modifiers", "notes"}
    with _LOCK:
        for entry in STORE["work_logs"]:
            if entry["id"] != entry_id or entry["agent_id"] != agent_id:
                continue
            if entry["status"] not in EDITABLE_STATUSES:
                return None
            for key, value in fields.items():
                if key in allowed:
                    entry[key] = list(value) if key == "modifiers" else value
            entry["points"] = mock_data.calculate_points(
                entry["job_type"], entry["modifiers"])
            # An edit after changes_requested puts it back in the agent's hands.
            if entry["status"] == STATUS_CHANGES:
                entry["status"] = STATUS_DRAFT
            return copy.deepcopy(entry)
    return None


def delete_entry(entry_id, agent_id):
    """Delete a draft the agent owns. Only drafts may be deleted."""
    with _LOCK:
        for index, entry in enumerate(STORE["work_logs"]):
            if entry["id"] == entry_id and entry["agent_id"] == agent_id:
                if entry["status"] != STATUS_DRAFT:
                    return False
                del STORE["work_logs"][index]
                return True
    return False


def submit_day(agent_id, on_date):
    """Move every draft on a date to submitted. Returns (count, points)."""
    with _LOCK:
        count = 0
        points = 0
        stamp = _stamp()
        for entry in STORE["work_logs"]:
            if (entry["agent_id"] == agent_id and entry["date"] == on_date
                    and entry["status"] == STATUS_DRAFT):
                entry["status"] = STATUS_SUBMITTED
                entry["submitted_at"] = stamp
                count += 1
                points += entry["points"]
        return count, points


def get_day_summary(agent_id, on_date):
    """Totals for one day. THE single source of truth for daily figures.

    Only APPROVED entries count toward jobs/minutes/points/value — the same
    "not banked yet" rule the dollar ledger uses. A day holding only drafts or
    submitted work reports zeroes, with pending_count saying why.

    draft_count / draft_points / submitted_at describe the day's workflow
    state and are deliberately separate from the approved totals.
    """
    with _LOCK:
        entries = [l for l in STORE["work_logs"]
                   if l["agent_id"] == agent_id and l["date"] == on_date]

    approved = [l for l in entries if l["status"] == STATUS_APPROVED]
    drafts = [l for l in entries if l["status"] == STATUS_DRAFT]
    submitted = [l for l in entries if l["status"] == STATUS_SUBMITTED]
    points = sum(l["points"] for l in approved)

    return {
        "jobs": len(approved),
        "minutes": sum(l["duration_minutes"] for l in approved),
        "points": points,
        "est_value": mock_data.points_to_usd(points),
        "pending_count": len(entries) - len(approved),
        "draft_count": len(drafts),
        "draft_points": sum(l["points"] for l in drafts),
        "submitted_at": submitted[0]["submitted_at"] if submitted else None,
    }


def agent_points_summary(agent_id):
    """Banked vs awaiting review, for the dollar ledger."""
    with _LOCK:
        entries = [l for l in STORE["work_logs"] if l["agent_id"] == agent_id]
        return {
            "approved_points": sum(l["points"] for l in entries
                                   if l["status"] == STATUS_APPROVED),
            "pending_points": sum(l["points"] for l in entries
                                  if l["status"] == STATUS_SUBMITTED),
        }


def get_submitted_for_manager(manager_id):
    """The manager's review queue, oldest submission first."""
    with _LOCK:
        entries = [l for l in STORE["work_logs"]
                   if l["manager_id"] == manager_id and l["status"] == STATUS_SUBMITTED]
        entries.sort(key=lambda l: (l["submitted_at"] or "", l["id"]))
        return copy.deepcopy(entries)


def count_submitted_for_manager(manager_id):
    with _LOCK:
        return sum(1 for l in STORE["work_logs"]
                   if l["manager_id"] == manager_id and l["status"] == STATUS_SUBMITTED)


# Older call sites used the "pending" vocabulary.
get_pending_logs_for_manager = get_submitted_for_manager
count_pending_logs_for_manager = count_submitted_for_manager


def review_entry(entry_id, status, reviewer_id, note=""):
    """Approve, reject, or send an entry back for changes."""
    if status not in (STATUS_APPROVED, STATUS_REJECTED, STATUS_CHANGES):
        raise ValueError(f"unknown review status: {status}")
    with _LOCK:
        for entry in STORE["work_logs"]:
            if entry["id"] == entry_id:
                if entry["status"] != STATUS_SUBMITTED:
                    return None
                entry["status"] = status
                entry["reviewer_id"] = reviewer_id
                entry["reviewed_at"] = _stamp()
                entry["review_note"] = note
                return copy.deepcopy(entry)
    return None


# --- Programs --------------------------------------------------------------
def get_programs(owner_id=None, status=None):
    """Programs, optionally by author (created_by) and status."""
    with _LOCK:
        programs = list(STORE["programs"])
        if owner_id is not None:
            programs = [p for p in programs if p["created_by"] == owner_id]
        if status:
            programs = [p for p in programs if p["status"] == status]
        return copy.deepcopy(programs)


def get_program(program_id):
    with _LOCK:
        return copy.deepcopy(
            next((p for p in STORE["programs"] if p["id"] == program_id), None))


def count_pending_programs():
    with _LOCK:
        return sum(1 for p in STORE["programs"] if p["status"] == PROGRAM_PENDING)


def add_program(name, owner_id, owner_name, team, budget, multiplier,
                starts, ends, summary, status=PROGRAM_PENDING):
    """Compact constructor kept for the older call sites and self-checks."""
    return create_program(
        owner_id, owner_name, name=name, description=summary, target_team=team,
        budget_estimate=budget, start_date=starts, end_date=ends, status=status)


def update_program_status(program_id, status, decided_by, decision_note=""):
    if status not in (PROGRAM_DRAFT, PROGRAM_PENDING, PROGRAM_APPROVED,
                      PROGRAM_REJECTED, PROGRAM_CHANGES):
        raise ValueError(f"unknown program status: {status}")
    with _LOCK:
        for program in STORE["programs"]:
            if program["id"] == program_id:
                program["status"] = status
                program["reviewed_by"] = decided_by
                program["reviewed_at"] = _stamp()
                program["director_note"] = decision_note
                return copy.deepcopy(program)
    return None


# --- Manager: burnout, team stats, review batches ---------------------------
def _consecutive_days_logged(entries, today):
    """Longest run of consecutive days with at least one entry, ending today
    or yesterday. A run that stopped earlier is not a current signal."""
    days = set()
    for entry in entries:
        try:
            days.add(datetime.strptime(entry["date"], "%Y-%m-%d").date())
        except (TypeError, ValueError):
            continue
    if not days:
        return 0
    latest = max(days)
    if (today - latest).days > 1:
        return 0
    run, cursor = 0, latest
    while cursor in days:
        run += 1
        cursor -= timedelta(days=1)
    return run


def get_burnout_signals(manager_id, today=None):
    """Agents showing strain, most severe first.

    Three triggers, all stated on the page so the manager can see the rule:
      * more than BURNOUT_OVERTIME_HOURS overtime hours this week
      * BURNOUT_CONSECUTIVE_DAYS or more consecutive days logged with no gap
      * a repeat rate more than BURNOUT_REPEAT_RATE_MARGIN points above the
        team average
    """
    today = today or date.today()
    reports = mock_data.reports_for_manager(manager_id)
    if not reports:
        return []

    team_repeat = sum(a["repeat_rate"] for a in reports) / len(reports)
    signals = []

    for agent in reports:
        entries = get_entries_for_agent(agent["id"])
        run = _consecutive_days_logged(entries, today)
        triggers = []

        overtime = agent["overtime_hours_this_week"]
        if overtime > mock_data.BURNOUT_OVERTIME_HOURS:
            triggers.append({
                "code": "overtime",
                "text": f"{overtime} hrs overtime this week",
                "weight": overtime - mock_data.BURNOUT_OVERTIME_HOURS,
            })
        if run >= mock_data.BURNOUT_CONSECUTIVE_DAYS:
            triggers.append({
                "code": "consecutive",
                "text": f"{run} consecutive days logged",
                "weight": run - mock_data.BURNOUT_CONSECUTIVE_DAYS,
            })
        margin = agent["repeat_rate"] - team_repeat
        if margin > mock_data.BURNOUT_REPEAT_RATE_MARGIN:
            triggers.append({
                "code": "repeat",
                "text": f"repeat rate {agent['repeat_rate']}% vs {team_repeat:.1f}% team average",
                "weight": margin,
            })

        if triggers:
            signals.append({
                "agent": dict(agent),
                "initials": "".join(part[0] for part in agent["name"].split()[:2]).upper(),
                "triggers": triggers,
                # Severity: how many rules fired, then by how much.
                "severity": (len(triggers), round(sum(t["weight"] for t in triggers), 1)),
            })

    signals.sort(key=lambda s: s["severity"], reverse=True)
    return signals


def get_team_stats(manager_id):
    """KPI figures for the team dashboard, with deltas against last month."""
    reports = mock_data.reports_for_manager(manager_id)
    if not reports:
        return {}
    count = len(reports)
    previous = mock_data.TEAM_PREVIOUS

    def delta(now, before):
        if not before:
            return 0.0
        return round((now - before) / before * 100, 1)

    points = sum(a["points"] for a in reports)
    repeat = round(sum(a["repeat_rate"] for a in reports) / count, 1)
    on_time = round(sum(a["on_time_rate"] for a in reports) / count, 1)
    jobs = sum(a["jobs_this_week"] for a in reports)
    csat = round(sum(a["csat"] for a in reports) / count, 2)
    pending = count_submitted_for_manager(manager_id)

    return {
        "team_size": count,
        "points": points,
        "points_delta": delta(points, previous["points"]),
        "repeat_rate": repeat,
        "repeat_delta": delta(repeat, previous["repeat_rate"]),
        "on_time_rate": on_time,
        "on_time_delta": delta(on_time, previous["on_time_rate"]),
        "jobs_this_week": jobs,
        "jobs_delta": delta(jobs, previous["jobs_this_week"]),
        "pending": pending,
        "csat": csat,
        "csat_delta": delta(csat, previous["csat"]),
    }


def review_batch(decisions, reviewer_id):
    """Commit a set of review decisions at once.

    `decisions` is [{entry_id, status, note}]. Reject and changes_requested
    without a note are refused here, not just in the browser — a decision with
    no reason is the opacity this portal exists to remove.
    Returns (applied, refused).
    """
    applied, refused = [], []
    for decision in decisions:
        status = decision.get("status")
        note = (decision.get("note") or "").strip()
        if status in (STATUS_REJECTED, STATUS_CHANGES) and not note:
            refused.append({"entry_id": decision.get("entry_id"), "reason": "note required"})
            continue
        result = review_entry(decision.get("entry_id"), status, reviewer_id, note)
        (applied if result else refused).append(
            result or {"entry_id": decision.get("entry_id"), "reason": "not reviewable"})
    return applied, refused


def get_reviewed_by(manager_id, since=None):
    """Decisions this manager has already made, newest first."""
    with _LOCK:
        entries = [l for l in STORE["work_logs"]
                   if l["reviewer_id"] == manager_id and l["reviewed_at"]]
        if since:
            entries = [l for l in entries if l["reviewed_at"] >= since]
        entries.sort(key=lambda l: l["reviewed_at"], reverse=True)
        return copy.deepcopy(entries)


REOPEN_WINDOW_HOURS = 24


def reopen_entry(entry_id, reviewer_id, note):
    """Send a decided entry back to changes_requested, within 24 hours.

    Requires a note for the same reason a rejection does.
    """
    note = (note or "").strip()
    if not note:
        return None
    with _LOCK:
        for entry in STORE["work_logs"]:
            if entry["id"] != entry_id or entry["reviewer_id"] != reviewer_id:
                continue
            try:
                decided = datetime.strptime(entry["reviewed_at"], "%Y-%m-%d %H:%M")
            except (TypeError, ValueError):
                return None
            if datetime.now() - decided > timedelta(hours=REOPEN_WINDOW_HOURS):
                return None
            entry["status"] = STATUS_CHANGES
            entry["review_note"] = note
            entry["reviewed_at"] = _stamp()
            return copy.deepcopy(entry)
    return None


# --- Manager: programs -----------------------------------------------------
def get_programs_for_manager(manager_id, status=None):
    return get_programs(owner_id=manager_id, status=status)


def create_program(created_by, owner_name, **fields):
    with _LOCK:
        program = {
            "id": next(_ids["programs"]),
            "created_by": created_by, "owner_name": owner_name,
            "created_at": date.today().isoformat(),
            "status": fields.pop("status", PROGRAM_DRAFT),
            "director_note": "", "reviewed_by": None, "reviewed_at": None,
            "name": "", "description": "", "start_date": "", "end_date": "",
            "target_scope": "team", "target_team": "", "job_types": [],
            "bonus_structure": [], "budget_estimate": 0,
            "expected_participants": 0, "success_metric": "", "success_target": 0,
        }
        program.update(fields)
        STORE["programs"].append(program)
        return copy.deepcopy(program)


EDITABLE_PROGRAM_STATUSES = (PROGRAM_DRAFT, PROGRAM_CHANGES)


def update_program(program_id, owner_id, **fields):
    """Edit a program the manager owns, only while it is editable."""
    with _LOCK:
        for program in STORE["programs"]:
            if program["id"] != program_id or program["created_by"] != owner_id:
                continue
            if program["status"] not in EDITABLE_PROGRAM_STATUSES:
                return None
            for key, value in fields.items():
                if key in program and key not in ("id", "created_by", "status"):
                    program[key] = value
            return copy.deepcopy(program)
    return None


def submit_program(program_id, owner_id):
    """Send a program up for director approval."""
    with _LOCK:
        for program in STORE["programs"]:
            if program["id"] != program_id or program["created_by"] != owner_id:
                continue
            if program["status"] not in EDITABLE_PROGRAM_STATUSES:
                return None
            program["status"] = PROGRAM_PENDING
            program["created_at"] = program["created_at"] or date.today().isoformat()
            return copy.deepcopy(program)
    return None


# --- Notifications ---------------------------------------------------------
def get_notifications(user_id, unread_only=False):
    with _LOCK:
        items = [n for n in STORE["notifications"] if n["user_id"] == user_id]
        if unread_only:
            items = [n for n in items if not n["read"]]
        return copy.deepcopy(items)


def add_notification(user_id, message, kind="info"):
    with _LOCK:
        item = {
            "id": next(_ids["notifications"]),
            "user_id": user_id, "message": message, "kind": kind,
            "read": False, "created_at": date.today().isoformat(),
        }
        STORE["notifications"].append(item)
        return copy.deepcopy(item)


def mark_notification_read(notification_id):
    with _LOCK:
        for item in STORE["notifications"]:
            if item["id"] == notification_id:
                item["read"] = True
                return copy.deepcopy(item)
    return None


if __name__ == "__main__":
    import os, django
    reset_store()
    today = date.today().isoformat()

    dana = get_entries_for_agent(417)
    assert len(dana) > 40, "three weeks of history"
    drafts = [e for e in dana if e["status"] == STATUS_DRAFT]
    assert len(drafts) == 2, "two drafts from today"
    assert all(e["date"] == today for e in drafts)
    assert sum(1 for e in dana if e["status"] == STATUS_REJECTED) == 2
    assert sum(1 for e in dana if e["status"] == STATUS_CHANGES) == 1
    assert count_submitted_for_manager(884) >= 5, "queue has content from other agents"

    # Reads hand back copies.
    dana[0]["points"] = 99999
    assert get_entries_for_agent(417)[0]["points"] != 99999

    # Points are recalculated on write, never taken from the caller.
    entry = add_entry(417, "Dana Whitfield", 884, today, "new_install_residential",
                      "WO-2026-9001", "1 Test St, Columbus", 90,
                      ["first_time_fix", "premium_upsell"])
    assert entry["points"] == 168 == mock_data.calculate_points(
        "new_install_residential", ["first_time_fix", "premium_upsell"])

    # Editing a draft recalculates.
    updated = update_entry(entry["id"], 417, modifiers=["safety_flagged"])
    assert updated["points"] == 0, "safety flag zeroes it"

    # Ownership is enforced in the store, not just the view.
    assert update_entry(entry["id"], 999, notes="hack") is None
    assert delete_entry(entry["id"], 999) is False

    # Submitting locks the entry.
    before = count_submitted_for_manager(884)
    count, points = submit_day(417, today)
    assert count == 3, count                    # 2 seeded drafts + the new one
    assert count_submitted_for_manager(884) == before + 3
    assert update_entry(entry["id"], 417, notes="late edit") is None, "submitted is locked"
    assert delete_entry(entry["id"], 417) is False

    # changes_requested reopens it for editing.
    sent_back = review_entry(entry["id"], STATUS_CHANGES, 884, "Add the suite number.")
    assert sent_back["status"] == STATUS_CHANGES
    assert sent_back["review_note"] == "Add the suite number."
    reopened = update_entry(entry["id"], 417, notes="fixed")
    assert reopened["status"] == STATUS_DRAFT, "editable again"
    assert reopened["review_note"] == "Add the suite number.", "reviewer note preserved"

    # Only submitted entries can be reviewed.
    assert review_entry(entry["id"], STATUS_APPROVED, 884) is None

    # Ledger split
    summary = agent_points_summary(417)
    assert summary["approved_points"] > 0 and summary["pending_points"] > 0
    assert summary["approved_points"] != summary["pending_points"]

    # Day summary counts APPROVED only
    day = get_day_summary(417, today)
    assert day["jobs"] == 0 and day["points"] == 0 and day["est_value"] == 0.0, day
    assert day["pending_count"] > 0, "pending work is reported, not counted"
    approved_day = next(e["date"] for e in get_entries_for_agent(417)
                        if e["status"] == STATUS_APPROVED)
    past = get_day_summary(417, approved_day)
    assert past["jobs"] > 0 and past["points"] > 0
    assert past["est_value"] == mock_data.points_to_usd(past["points"])

    # Programs still work
    assert count_pending_programs() == 2
    program = add_program("Test", 884, "Marcus Vale", "Columbus North", 1000, 1.1,
                          "2026-09-01", "2026-09-30", "test")
    assert count_pending_programs() == 3
    update_program_status(program["id"], PROGRAM_APPROVED, "Priya Raghunathan")
    assert count_pending_programs() == 2

    add_notification(417, "hello")
    assert len(get_notifications(417, unread_only=True)) == 1

    reset_store()
    assert len([e for e in get_entries_for_agent(417)
                if e["status"] == STATUS_DRAFT]) == 2, "reset restores seed"
    assert get_notifications(417) == []
    print("store OK")
