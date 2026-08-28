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
        "programs": [
            {"id": 1, "name": "Q4 Upsell Accelerator", "owner_id": 884,
             "owner_name": "Marcus Vale", "team": "Columbus North",
             "budget": 45000, "multiplier": 1.5, "starts": "2026-10-01",
             "ends": "2026-12-31", "status": PROGRAM_PENDING,
             "summary": "Double points on mobile line attachments through Q4.",
             "submitted_at": "2026-08-20 11:30", "decided_by": None,
             "decided_at": None, "decision_note": ""},
            {"id": 2, "name": "Safety Streak Bonus", "owner_id": 885,
             "owner_name": "Deirdre Kwan", "team": "Cleveland East",
             "budget": 18000, "multiplier": 1.25, "starts": "2026-09-01",
             "ends": "2026-11-30", "status": PROGRAM_PENDING,
             "summary": "Bonus points for six consecutive clean safety audits.",
             "submitted_at": "2026-08-22 14:05", "decided_by": None,
             "decided_at": None, "decision_note": ""},
            {"id": 3, "name": "Summer Install Sprint", "owner_id": 884,
             "owner_name": "Marcus Vale", "team": "Columbus North",
             "budget": 32000, "multiplier": 1.25, "starts": "2026-06-01",
             "ends": "2026-08-31", "status": PROGRAM_APPROVED,
             "summary": "Seasonal multiplier on completed installs.",
             "submitted_at": "2026-05-12 09:40", "decided_by": "Priya Raghunathan",
             "decided_at": "2026-05-14 16:20", "decision_note": "Approved at full budget."},
            {"id": 4, "name": "Weekend Coverage Pilot", "owner_id": 886,
             "owner_name": "Hollis Barrera", "team": "Toledo West",
             "budget": 26000, "multiplier": 1.5, "starts": "2026-07-01",
             "ends": "2026-09-30", "status": PROGRAM_REJECTED,
             "summary": "Premium points for Saturday appointment slots.",
             "submitted_at": "2026-06-02 10:15", "decided_by": "Priya Raghunathan",
             "decided_at": "2026-06-05 11:00",
             "decision_note": "Overlaps the install sprint; resubmit for Q1."},
        ],
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
    with _LOCK:
        programs = list(STORE["programs"])
        if owner_id is not None:
            programs = [p for p in programs if p["owner_id"] == owner_id]
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
    with _LOCK:
        program = {
            "id": next(_ids["programs"]),
            "name": name, "owner_id": owner_id, "owner_name": owner_name,
            "team": team, "budget": budget, "multiplier": multiplier,
            "starts": starts, "ends": ends, "status": status, "summary": summary,
            "submitted_at": date.today().isoformat(),
            "decided_by": None, "decided_at": None, "decision_note": "",
        }
        STORE["programs"].append(program)
        return copy.deepcopy(program)


def update_program_status(program_id, status, decided_by, decision_note=""):
    if status not in (PROGRAM_DRAFT, PROGRAM_PENDING, PROGRAM_APPROVED, PROGRAM_REJECTED):
        raise ValueError(f"unknown program status: {status}")
    with _LOCK:
        for program in STORE["programs"]:
            if program["id"] == program_id:
                program["status"] = status
                program["decided_by"] = decided_by
                program["decided_at"] = date.today().isoformat()
                program["decision_note"] = decision_note
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
