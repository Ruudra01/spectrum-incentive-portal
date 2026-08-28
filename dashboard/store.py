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
import threading
from datetime import date

_LOCK = threading.Lock()

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

PROGRAM_DRAFT = "draft"
PROGRAM_PENDING = "pending"
PROGRAM_APPROVED = "approved"
PROGRAM_REJECTED = "rejected"


def _seed():
    """The state a fresh process (or a reset) starts from."""
    return {
        "work_logs": [
            {"id": 1, "agent_id": 417, "agent_name": "Dana Whitfield", "manager_id": 884,
             "job_type": "Install", "job_date": "2026-08-24", "hours": 7.5, "overtime": 0.0,
             "points_claimed": 120, "notes": "Triple-play install, Grandview.",
             "status": STATUS_APPROVED, "submitted_at": "2026-08-24 17:10",
             "decided_by": "Marcus Vale", "decided_at": "2026-08-25 08:02",
             "decision_note": ""},
            {"id": 2, "agent_id": 417, "agent_name": "Dana Whitfield", "manager_id": 884,
             "job_type": "Upsell", "job_date": "2026-08-26", "hours": 6.0, "overtime": 1.5,
             "points_claimed": 90, "notes": "Added mobile line at service call.",
             "status": STATUS_PENDING, "submitted_at": "2026-08-26 18:40",
             "decided_by": None, "decided_at": None, "decision_note": ""},
            {"id": 3, "agent_id": 803, "agent_name": "Ibrahim Cole", "manager_id": 884,
             "job_type": "Service call", "job_date": "2026-08-26", "hours": 9.0, "overtime": 2.5,
             "points_claimed": 70, "notes": "Two rollbacks on the same node.",
             "status": STATUS_PENDING, "submitted_at": "2026-08-26 20:15",
             "decided_by": None, "decided_at": None, "decision_note": ""},
            {"id": 4, "agent_id": 521, "agent_name": "Sofia Marchetti", "manager_id": 884,
             "job_type": "Install", "job_date": "2026-08-27", "hours": 8.5, "overtime": 3.0,
             "points_claimed": 110, "notes": "Late finish, customer rescheduled twice.",
             "status": STATUS_PENDING, "submitted_at": "2026-08-27 19:05",
             "decided_by": None, "decided_at": None, "decision_note": ""},
            {"id": 5, "agent_id": 288, "agent_name": "Grace Okonkwo", "manager_id": 884,
             "job_type": "Install", "job_date": "2026-08-21", "hours": 7.0, "overtime": 0.5,
             "points_claimed": 100, "notes": "",
             "status": STATUS_REJECTED, "submitted_at": "2026-08-21 17:55",
             "decided_by": "Marcus Vale", "decided_at": "2026-08-22 09:14",
             "decision_note": "Job already credited on log #0."},
        ],
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
def get_logs_for_agent(agent_id):
    with _LOCK:
        return copy.deepcopy([l for l in STORE["work_logs"] if l["agent_id"] == agent_id])


def get_logs_for_manager(manager_id, status=None):
    with _LOCK:
        logs = [l for l in STORE["work_logs"] if l["manager_id"] == manager_id]
        if status:
            logs = [l for l in logs if l["status"] == status]
        return copy.deepcopy(logs)


def get_pending_logs_for_manager(manager_id):
    return get_logs_for_manager(manager_id, status=STATUS_PENDING)


def count_pending_logs_for_manager(manager_id):
    with _LOCK:
        return sum(
            1 for l in STORE["work_logs"]
            if l["manager_id"] == manager_id and l["status"] == STATUS_PENDING
        )


def add_log(agent_id, agent_name, manager_id, job_type, job_date, hours,
            overtime, points_claimed, notes=""):
    with _LOCK:
        log = {
            "id": next(_ids["work_logs"]),
            "agent_id": agent_id, "agent_name": agent_name, "manager_id": manager_id,
            "job_type": job_type, "job_date": job_date,
            "hours": hours, "overtime": overtime, "points_claimed": points_claimed,
            "notes": notes, "status": STATUS_PENDING,
            "submitted_at": date.today().isoformat(),
            "decided_by": None, "decided_at": None, "decision_note": "",
        }
        STORE["work_logs"].append(log)
        return copy.deepcopy(log)


def update_log_status(log_id, status, decided_by, decision_note=""):
    """Approve or reject a log. Returns the updated copy, or None if unknown."""
    if status not in (STATUS_APPROVED, STATUS_REJECTED, STATUS_PENDING):
        raise ValueError(f"unknown status: {status}")
    with _LOCK:
        for log in STORE["work_logs"]:
            if log["id"] == log_id:
                log["status"] = status
                log["decided_by"] = decided_by
                log["decided_at"] = date.today().isoformat()
                log["decision_note"] = decision_note
                return copy.deepcopy(log)
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
    reset_store()
    assert count_pending_logs_for_manager(884) == 3
    assert len(get_logs_for_agent(417)) == 2
    assert count_pending_programs() == 2

    # Helpers hand back copies — mutating a result must not touch the store.
    logs = get_logs_for_agent(417)
    logs[0]["points_claimed"] = 99999
    assert get_logs_for_agent(417)[0]["points_claimed"] != 99999

    log = add_log(417, "Dana Whitfield", 884, "Install", "2026-08-28", 8.0, 1.0, 130, "test")
    assert count_pending_logs_for_manager(884) == 4
    assert update_log_status(log["id"], STATUS_APPROVED, "Marcus Vale")["status"] == "approved"
    assert count_pending_logs_for_manager(884) == 3
    assert update_log_status(99999, STATUS_APPROVED, "x") is None

    program = add_program("Test", 884, "Marcus Vale", "Columbus North", 1000, 1.1,
                          "2026-09-01", "2026-09-30", "test")
    assert count_pending_programs() == 3
    update_program_status(program["id"], PROGRAM_APPROVED, "Priya Raghunathan")
    assert count_pending_programs() == 2

    add_notification(417, "hello")
    assert len(get_notifications(417, unread_only=True)) == 1

    reset_store()
    assert count_pending_logs_for_manager(884) == 3, "reset restores seed"
    assert get_notifications(417) == []
    print("store OK")
