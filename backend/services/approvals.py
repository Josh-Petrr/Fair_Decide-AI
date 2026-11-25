"""Allocation workflow: the project head requests -> approvers sign off -> the head sends.

Who approves (each person only once, never the requester):
  - the project head's own manager, if there is one
  - if the employee is in another team: the employee's manager, and the person above that manager
"Manager" means the nearest person up the reporting line with a manager login; team leads have no account.
Nothing touches assignments or email until the head presses send, which runs decisions.decide()."""
import json

from fastapi import HTTPException

from .. import events
from ..db import conn, fetch_all, fetch_one
from ..engine import filters
from ..engine.store import today_ordinal
from . import decisions

ITEM = """
    SELECT r.allocation_id, r.status, r.reason, r.notes, r.source, r.created_at, r.project_role_id, r.employee_id, r.requested_by,
           e.full_name AS employee_name, e.designation, l.current_allocation_pct AS workload, pr.role_title, pr.allocation_pct,
           GREATEST(pr.start_date, fd_as_of()) AS start_date, p.project_id, p.project_name, u.full_name AS requester,
           (SELECT json_agg(json_build_object('user_id', a.approver_id, 'name', au.full_name, 'relation', a.relation,
                                              'status', a.status, 'comment', a.comment) ORDER BY a.position)
              FROM allocation_approvals a JOIN app_users au ON au.user_id = a.approver_id
             WHERE a.allocation_id = r.allocation_id) AS approvers
    FROM allocation_requests r
    JOIN employees e USING (employee_id) JOIN project_roles pr USING (project_role_id) JOIN projects p USING (project_id)
    JOIN app_users u ON u.user_id = r.requested_by
    LEFT JOIN v_employee_current_load l ON l.employee_id = r.employee_id"""


def load_org():
    rows = fetch_all("""SELECT e.employee_id, e.full_name, e.first_name, e.designation, e.reporting_manager_id, e.employment_status, u.user_id
                        FROM employees e LEFT JOIN app_users u ON u.employee_id = e.employee_id AND u.is_active AND u.app_role = 'manager'
                        WHERE e.employment_status <> 'Exited'""")
    return {r["employee_id"]: r for r in rows}


def _managers_above(org, employee_id):
    """Active managers with a login above this person, nearest first."""
    out, seen, boss = [], {employee_id}, org[employee_id]["reporting_manager_id"]
    while boss in org and boss not in seen:
        seen.add(boss)
        if org[boss]["user_id"] and org[boss]["employment_status"] == "Active":
            out.append(org[boss])
        boss = org[boss]["reporting_manager_id"]
    return out


def route(org, head_id, employee_id):
    """Ordered approvers for putting this employee on a project led by head_id."""
    mine, theirs = _managers_above(org, head_id), _managers_above(org, employee_id)
    same_team = any(m["employee_id"] == head_id for m in theirs) or bool(
        mine and theirs and mine[0]["employee_id"] == theirs[0]["employee_id"])
    steps = [(mine[0], "Your manager")] if mine else []
    if not same_team:
        first = org[employee_id]["first_name"]
        steps += zip(theirs[:2], (f"{first}'s manager", f"Above {first}'s manager"))
    out = {}
    for m, relation in steps:
        if m["employee_id"] != head_id:
            out.setdefault(m["user_id"], dict(user_id=m["user_id"], name=m["full_name"], designation=m["designation"], relation=relation))
    return list(out.values())


def access(user, role_id, candidates):
    """Adds approvers to each candidate for the head, and says what this user may do on the demand."""
    with conn() as c:
        head = decisions.project_head(c, role_id)
    can = user["app_role"] == "manager" and bool(head) and head["employee_id"] == user["employee_id"]
    if can:
        org = load_org()
        for cand in candidates:
            cand["approvers"] = route(org, user["employee_id"], cand["employee_id"])
    rows = fetch_all("SELECT employee_id, status FROM allocation_requests WHERE project_role_id = %s AND status IN ('pending', 'approved')", (role_id,))
    return dict(can_allocate=can, can_suggest=user["app_role"] == "manager" and not can, head=head["full_name"] if head else None, open_requests={r["employee_id"]: r["status"] for r in rows})


def _publish(title, users, role_id):
    events.publish("allocation", dict(title=title, users=list(users), role_id=role_id))


def _audit(c, event, user_id, allocation_id, **payload):
    c.execute("INSERT INTO audit_log (event_type, actor, entity, entity_id, payload) VALUES (%s, %s, 'allocation', %s, %s)",
              (event, user_id, str(allocation_id), json.dumps(payload)))


def request(rec, user, role_id, employee_ids, reason, request_id=None, notes=None, offered_by=None, source="shortlist"):
    """offered_by: the manager who offered this person; their own sign-off is taken as given, nobody else's."""
    if not reason or len(reason.strip()) < 5:
        raise HTTPException(422, "Please record a reason for this decision (at least 5 characters).")
    if not employee_ids:
        raise HTTPException(422, "Select at least one employee.")
    org = load_org()
    created = []
    with rec.lock, conn() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", (decisions.DECISION_LOCK,))
        rec.store.refresh()
        st = rec.store
        if role_id not in st.roles:
            raise HTTPException(404, "Demand not found")
        decisions.require_head(c, user, role_id)
        role = st.role_spec(role_id)
        filled = sum(1 for a in st.asg if a["project_role_id"] == role_id and a["status"] in ("Upcoming", "Active"))
        taken = {r["employee_id"] for r in c.execute(
            "SELECT employee_id FROM allocation_requests WHERE project_role_id = %s AND status IN ('pending', 'approved')", (role_id,)).fetchall()}
        if taken & set(employee_ids):
            raise HTTPException(409, "A request for this person is already in progress.")
        remaining = role["headcount"] - filled - len(taken)
        if len(employee_ids) > remaining:
            raise HTTPException(409, f"Only {remaining} open position(s) left on this demand.")
        problems = {st.emp[e]["full_name"]: filters.check(st, role, e, today_ordinal())[0] for e in employee_ids}
        problems = {k: v for k, v in problems.items() if v}
        if problems:
            raise HTTPException(409, {"message": "Some selections are no longer eligible", "details": problems})
        for eid in employee_ids:
            approvers = route(org, user["employee_id"], eid)
            aid = c.execute("""INSERT INTO allocation_requests (request_id, project_role_id, employee_id, requested_by, reason, notes, source, status)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING allocation_id""",
                            (request_id, role_id, eid, user["user_id"], reason, notes, source,
                             "pending" if any(a["user_id"] != offered_by for a in approvers) else "approved")).fetchone()["allocation_id"]
            for pos, a in enumerate(approvers):
                auto = a["user_id"] == offered_by
                c.execute("""INSERT INTO allocation_approvals (allocation_id, approver_id, position, relation, status, comment, decided_at)
                             VALUES (%s,%s,%s,%s,%s,%s, CASE WHEN %s THEN now() END)""",
                          (aid, a["user_id"], pos, a["relation"], "approved" if auto else "pending", "Offered this person" if auto else None, auto))
            _audit(c, "allocation_requested", user["user_id"], aid, employee=eid, role=role_id, source=source, reason=reason,
                   approvers=[a["user_id"] for a in approvers])
            created.append(dict(allocation_id=aid, employee_id=eid, employee_name=st.emp[eid]["full_name"], approvers=approvers))
    _publish(f"New approval request from {user['full_name']}", {a["user_id"] for r in created for a in r["approvers"]} - {offered_by}, role_id)
    return dict(requests=created)


def respond(user, allocation_id, approve, comment=None):
    if not approve and len((comment or "").strip()) < 5:
        raise HTTPException(422, "Please give a reason for rejecting (at least 5 characters).")
    with conn() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", (decisions.DECISION_LOCK,))
        r = c.execute("SELECT * FROM allocation_requests WHERE allocation_id = %s", (allocation_id,)).fetchone()
        mine = r and c.execute("SELECT status FROM allocation_approvals WHERE allocation_id = %s AND approver_id = %s",
                               (allocation_id, user["user_id"])).fetchone()
        if not mine:
            raise HTTPException(403, "This request is not waiting for your approval.")
        if r["status"] != "pending" or mine["status"] != "pending":
            raise HTTPException(409, "This request has already been decided.")
        c.execute("UPDATE allocation_approvals SET status = %s, comment = %s, decided_at = now() WHERE allocation_id = %s AND approver_id = %s",
                  ("approved" if approve else "rejected", comment, allocation_id, user["user_id"]))
        left = c.execute("SELECT count(*) AS n FROM allocation_approvals WHERE allocation_id = %s AND status = 'pending'",
                         (allocation_id,)).fetchone()["n"]
        status = "rejected" if not approve else "pending" if left else "approved"
        if status != "pending":
            c.execute("UPDATE allocation_requests SET status = %s, updated_at = now() WHERE allocation_id = %s", (status, allocation_id))
        if status == "rejected":
            c.execute("UPDATE allocation_approvals SET status = 'closed' WHERE allocation_id = %s AND status = 'pending'", (allocation_id,))
        _audit(c, "allocation_" + ("approved_by" if approve else "rejected_by"), user["user_id"], allocation_id, comment=comment, status=status)
    title = {"approved": "All approvals in - ready to send", "rejected": f"Allocation rejected by {user['full_name']}",
             "pending": f"{user['full_name']} approved your request"}[status]
    _publish(title, [r["requested_by"]], r["project_role_id"])
    return dict(status=status)


def _own(c, user, allocation_id):
    r = c.execute("SELECT * FROM allocation_requests WHERE allocation_id = %s", (allocation_id,)).fetchone()
    if not r or r["requested_by"] != user["user_id"]:
        raise HTTPException(403, "Only the manager who made this request can do that.")
    return r


def send(rec, user, allocation_id, emails=None):
    """Claims the approved request so it cannot be sent twice, then assigns and queues the email."""
    with conn() as c:
        r = _own(c, user, allocation_id)
        if not c.execute("UPDATE allocation_requests SET status = 'sent', updated_at = now() WHERE allocation_id = %s AND status = 'approved' RETURNING 1",
                         (allocation_id,)).fetchone():
            raise HTTPException(409, "This request is not ready to send.")
    try:
        result = decisions.decide(rec, user, r["project_role_id"], "approve", [r["employee_id"]], r["reason"], r["request_id"], r["notes"], emails)
    except HTTPException:
        with conn() as c:
            c.execute("UPDATE allocation_requests SET status = 'approved' WHERE allocation_id = %s", (allocation_id,))
        raise
    with conn() as c:
        c.execute("UPDATE allocation_requests SET decision_id = %s WHERE allocation_id = %s", (result["decision_id"], allocation_id))
    return result


def cancel(user, allocation_id):
    with conn() as c:
        r = _own(c, user, allocation_id)
        if not c.execute("UPDATE allocation_requests SET status = 'cancelled', updated_at = now() WHERE allocation_id = %s AND status IN ('pending', 'approved') RETURNING 1",
                         (allocation_id,)).fetchone():
            raise HTTPException(409, "This request can no longer be cancelled.")
        c.execute("UPDATE allocation_approvals SET status = 'closed' WHERE allocation_id = %s AND status = 'pending'", (allocation_id,))
        _audit(c, "allocation_cancelled", user["user_id"], allocation_id)
    _publish(f"{user['full_name']} cancelled a request", [], r["project_role_id"])
    return dict(status="cancelled")


def bench_team(rec, user, role_id):
    """Free people below this manager, with whether each one passes the demand's rules."""
    org = load_org()
    free = fetch_all("""SELECT l.employee_id FROM v_employee_current_load l JOIN employees e USING (employee_id)
                         WHERE l.current_allocation_pct = 0 AND e.employment_status = 'Active'""")
    mine = [r["employee_id"] for r in free if any(m["user_id"] == user["user_id"] for m in _managers_above(org, r["employee_id"]))]
    with rec.lock:
        role = rec.store.role_spec(role_id)
        out = []
        for eid in mine:
            blockers = filters.check(rec.store, role, eid, today_ordinal())[0]
            out.append(dict(employee_id=eid, name=org[eid]["full_name"], designation=org[eid]["designation"], blockers=blockers))
    return sorted(out, key=lambda x: (bool(x["blockers"]), x["name"]))


def suggest(rec, user, role_id, employee_ids, note=None):
    if not employee_ids:
        raise HTTPException(422, "Select at least one person.")
    if role_id not in rec.store.roles:
        raise HTTPException(404, "Demand not found")
    allowed = {p["employee_id"] for p in bench_team(rec, user, role_id) if not p["blockers"]}
    if not set(employee_ids) <= allowed:
        raise HTTPException(403, "You can only suggest free, eligible people from your own team.")
    with conn() as c:
        head = decisions.project_head(c, role_id)
        if head["employee_id"] == user["employee_id"]:
            raise HTTPException(409, "This is your own project: select the person directly.")
        to = c.execute("SELECT user_id FROM app_users WHERE employee_id = %s AND is_active", (head["employee_id"],)).fetchone()
        if not to:
            raise HTTPException(409, f"{head['full_name']} has no login to receive this.")
        for eid in employee_ids:
            done = c.execute("""INSERT INTO staffing_suggestions (project_role_id, employee_id, suggested_by, suggested_to, note)
                                 VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING suggestion_id""",
                             (role_id, eid, user["user_id"], to["user_id"], note)).fetchone()
            if done:
                _audit(c, "staffing_suggested", user["user_id"], done["suggestion_id"], employee=eid, role=role_id)
    _publish(f"{user['full_name']} has someone free for your project", [to["user_id"]], role_id)
    return dict(sent_to=head["full_name"])


def _suggestion(c, user, suggestion_id):
    s = c.execute("SELECT * FROM staffing_suggestions WHERE suggestion_id = %s", (suggestion_id,)).fetchone()
    if not s or s["suggested_to"] != user["user_id"]:
        raise HTTPException(403, "This suggestion was not sent to you.")
    if s["status"] != "new":
        raise HTTPException(409, "This suggestion has already been handled.")
    return s


def close_suggestion(rec, user, suggestion_id, accept):
    """Accepting raises a normal allocation request, so the usual approvals still apply."""
    with conn() as c:
        s = _suggestion(c, user, suggestion_id)
        by = c.execute("SELECT full_name FROM app_users WHERE user_id = %s", (s["suggested_by"],)).fetchone()["full_name"]
    if accept:
        request(rec, user, s["project_role_id"], [s["employee_id"]], f"Suggested by {by}" + (f": {s['note']}" if s["note"] else ""),
                offered_by=s["suggested_by"], source="suggestion")
    with conn() as c:
        c.execute("UPDATE staffing_suggestions SET status = %s WHERE suggestion_id = %s", ("accepted" if accept else "dismissed", suggestion_id))
    _publish(f"{user['full_name']} {'accepted' if accept else 'declined'} your suggestion", [s["suggested_by"]], s["project_role_id"])
    return dict(status="accepted" if accept else "dismissed")


def _suggestions(user):
    rows = fetch_all("""SELECT s.suggestion_id, s.project_role_id, s.employee_id, s.note, e.full_name AS employee_name, e.designation,
                               pr.role_title, p.project_name, u.full_name AS suggested_by, s.suggested_by AS offered_by
                        FROM staffing_suggestions s JOIN employees e USING (employee_id) JOIN project_roles pr USING (project_role_id)
                        JOIN projects p USING (project_id) JOIN app_users u ON u.user_id = s.suggested_by
                        WHERE s.suggested_to = %s AND s.status = 'new' ORDER BY s.created_at""", (user["user_id"],))
    if rows:
        org = load_org()
        for r in rows:
            r["approvers"] = [dict(a, status="approved" if a["user_id"] == r["offered_by"] else "pending")
                              for a in route(org, user["employee_id"], r["employee_id"])]
    return rows


def inbox(user):
    uid = user["user_id"]
    mine = lambda status, tail="r.created_at DESC": fetch_all(f"{ITEM} WHERE r.requested_by = %s AND r.status = %s ORDER BY {tail} LIMIT 20", (uid, status))
    return dict(
        to_approve=fetch_all(f"""{ITEM} WHERE r.status = 'pending' AND EXISTS (SELECT 1 FROM allocation_approvals a
                                 WHERE a.allocation_id = r.allocation_id AND a.approver_id = %s AND a.status = 'pending')
                                 ORDER BY r.created_at""", (uid,)),
        ready=mine("approved"), waiting=mine("pending"), rejected=mine("rejected")[:5], suggestions=_suggestions(user))
