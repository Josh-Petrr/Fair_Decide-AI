"""Human-in-the-loop decision: one atomic transaction writes assignments, demand status, decision, audit and
queued notifications. Eligibility is re-checked under a database lock, so two managers cannot double-book."""
import json
from datetime import date

from fastapi import HTTPException

from .. import events
from ..db import conn
from ..engine import filters
from ..engine.store import from_ordinal, today_ordinal
from . import notifier

DECISION_LOCK = 4242   # pg advisory lock id serialising all assignment decisions


def _next_id(c, table, col, prefix, width):
    m = c.execute(f"SELECT max(substr({col}, %s)::int) AS m FROM {table} WHERE {col} LIKE %s",
                  (len(prefix) + 1, prefix + "%")).fetchone()["m"] or 0
    return lambda k: f"{prefix}{m + k:0{width}d}"


def decide(rec, user, role_id, decision, employee_ids, reason, request_id=None, notes=None, emails=None):
    """emails: optional {employee_id: {"subject": .., "body": ..}} edited by the manager."""
    if not reason or len(reason.strip()) < 5:
        raise HTTPException(422, "Please record a reason for this decision (at least 5 characters).")
    if decision not in ("approve", "reject"):
        raise HTTPException(422, "decision must be 'approve' or 'reject'")
    if decision == "approve" and not employee_ids:
        raise HTTPException(422, "Select at least one employee to approve.")
    emails = emails or {}
    with rec.lock, conn() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", (DECISION_LOCK,))
        rec.store.refresh()                                     # see every assignment committed so far
        st, today = rec.store, today_ordinal()
        if role_id not in st.roles:
            raise HTTPException(404, "Demand not found")
        role = st.role_spec(role_id)
        filled = sum(1 for a in st.asg if a["project_role_id"] == role_id and a["status"] in ("Upcoming", "Active"))
        remaining = role["headcount"] - filled

        if decision == "reject":
            d = c.execute("""INSERT INTO assignment_decisions (request_id, project_role_id, decided_by, decision, decision_reason, notes)
                             VALUES (%s, %s, %s, 'rejected', %s, %s) RETURNING decision_id""",
                          (request_id, role_id, user["user_id"], reason, notes)).fetchone()["decision_id"]
            c.execute("INSERT INTO audit_log (event_type, actor, entity, entity_id, payload) VALUES (%s, %s, 'project_role', %s, %s)",
                      ("recommendation_rejected", user["user_id"], role_id, json.dumps({"decision_id": d, "reason": reason})))
            result = dict(decision_id=d, decision="rejected", assignments=[])
        else:
            if len(employee_ids) > remaining:
                raise HTTPException(409, f"Only {remaining} open position(s) left on this demand.")
            problems = {eid: filters.check(st, role, eid, today)[0] for eid in employee_ids}
            problems = {st.emp[k]["full_name"]: v for k, v in problems.items() if v}
            if problems:
                raise HTTPException(409, {"message": "Some selections are no longer eligible", "details": problems})
            recommended = set()
            if request_id:
                recommended = {r["employee_id"] for r in c.execute(
                    "SELECT employee_id FROM recommendation_candidates WHERE request_id = %s", (request_id,)).fetchall()}
            kind = "approved" if set(employee_ids) <= recommended else "modified"

            start = from_ordinal(max(role["start"], today))
            end = from_ordinal(role["end"])
            status = "Upcoming" if start > from_ordinal(today) else "Active"
            asg_id = _next_id(c, "assignments", "assignment_id", "ASG", 5)
            new_ids = []
            for k, eid in enumerate(employee_ids, start=1):
                c.execute("""INSERT INTO assignments (assignment_id, employee_id, project_id, project_role_id, role_title,
                                 allocation_pct, start_date, end_date, status, billable, assigned_by, assigned_on)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,%s)""",
                          (asg_id(k), eid, role["project_id"], role_id, role["title"], role["alloc"], start, end, status,
                           user["employee_id"], from_ordinal(today)))
                new_ids.append(asg_id(k))
            filled_now = filled + len(employee_ids)
            c.execute("UPDATE project_roles SET demand_status = %s WHERE project_role_id = %s",
                      ("Filled" if filled_now >= role["headcount"] else "Partially Filled", role_id))
            d = c.execute("""INSERT INTO assignment_decisions (request_id, project_role_id, decided_by, decision,
                                 selected_employee_ids, decision_reason, notes)
                             VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING decision_id""",
                          (request_id, role_id, user["user_id"], kind, employee_ids, reason, notes)).fetchone()["decision_id"]

            details = c.execute("""SELECT e.employee_id, e.first_name, e.email, a.assignment_id, p.project_name,
                                          cl.client_name, p.delivery_location, a.role_title, a.start_date, a.end_date,
                                          a.allocation_pct
                                   FROM assignments a JOIN employees e USING (employee_id)
                                   JOIN projects p USING (project_id) JOIN clients cl ON cl.client_id = p.client_id
                                   WHERE a.assignment_id = ANY(%s)""", (new_ids,)).fetchall()
            note_ids, note_of = [], {}
            for n in details:
                subject, body = notifier.compose(dict(n, manager_name=user["full_name"]))
                custom = emails.get(n["employee_id"]) or {}
                status_n = "queued" if n["email"] else "failed"
                note_ids.append(c.execute(
                    """INSERT INTO notifications (decision_id, assignment_id, employee_id, recipient, subject, body, status, error)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING notification_id""",
                    (d, n["assignment_id"], n["employee_id"], n["email"], custom.get("subject") or subject,
                     custom.get("body") or body, status_n, None if n["email"] else "No email on record")).fetchone()["notification_id"])
                note_of[n["employee_id"]] = note_ids[-1]
            c.execute("INSERT INTO audit_log (event_type, actor, entity, entity_id, payload) VALUES (%s, %s, 'project_role', %s, %s)",
                      ("assignment_" + kind, user["user_id"], role_id,
                       json.dumps({"decision_id": d, "employees": employee_ids, "assignments": new_ids, "reason": reason})))
            result = dict(decision_id=d, decision=kind, assignments=new_ids, notifications=note_ids, notification_of=note_of)
    # committed - now update the in-memory engine, tell every browser, and send emails in the background
    rec.refresh()
    events.publish("decision", dict(result, role_id=role_id, employee_ids=employee_ids, by=user["full_name"],
                                    at=str(date.today())))
    return result
