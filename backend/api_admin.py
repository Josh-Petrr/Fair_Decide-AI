"""Admin: manage logins, managers and employees, and hand a leaving manager's work to a successor.
Only the admin role can call these. Every change is written to the audit log."""
import json
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import events, state
from .auth import admin
from .db import conn, fetch_all, fetch_one
from .services import decisions

router = APIRouter(prefix="/api/admin")
LABELS = {1: "Beginner", 2: "Elementary", 3: "Intermediate", 4: "Advanced", 5: "Expert"}
OPEN = "('Active', 'Pipeline', 'On Hold')"


def _audit(c, event, user, entity, entity_id, **payload):
    c.execute("INSERT INTO audit_log (event_type, actor, entity, entity_id, payload) VALUES (%s, %s, %s, %s, %s)",
              (event, user["user_id"], entity, entity_id, json.dumps(payload, default=str)))


def _reload():
    with state.rec.lock:
        state.rec.store.load_static()
        state.rec.store.refresh()


def _next_user_id(c):
    return f"USR{c.execute('SELECT max(substr(user_id, 4)::int) AS m FROM app_users').fetchone()['m'] + 1:03d}"


def _create_manager(c, admin_user, employee_id, start):
    e = c.execute("SELECT * FROM employees WHERE employee_id = %s", (employee_id,)).fetchone()
    if not e or e["employment_status"] != "Active":
        raise HTTPException(409, "Only an active employee can become a manager.")
    if c.execute("SELECT 1 FROM app_users WHERE employee_id = %s", (employee_id,)).fetchone():
        raise HTTPException(409, f"{e['full_name']} already has a login.")
    if not e["email"]:
        raise HTTPException(422, f"{e['full_name']} has no email on record.")
    uid = _next_user_id(c)
    c.execute("""INSERT INTO app_users (user_id, employee_id, full_name, email, app_role, is_active, start_date)
                 VALUES (%s, %s, %s, %s, 'manager', true, %s)""", (uid, employee_id, e["full_name"], e["email"], start))
    _audit(c, "manager_added", admin_user, "app_user", uid, employee=employee_id, start_date=start)
    return uid


# ------------------------------------------------------------------ users and managers
@router.get("/users")
def users(user=Depends(admin)):
    return fetch_all(f"""
        SELECT u.user_id, u.full_name, u.app_role, u.is_active, u.start_date, u.end_date, u.employee_id,
               e.designation, e.job_level, m.full_name AS reports_to,
               (SELECT count(*) FROM projects p WHERE p.project_manager_id = u.employee_id AND p.status IN {OPEN}) AS projects,
               (SELECT count(*) FROM employees x WHERE x.reporting_manager_id = u.employee_id AND x.employment_status <> 'Exited') AS reports,
               (SELECT count(*) FROM allocation_approvals a JOIN allocation_requests r USING (allocation_id)
                 WHERE a.approver_id = u.user_id AND a.status = 'pending' AND r.status = 'pending') AS approvals
        FROM app_users u LEFT JOIN employees e USING (employee_id) LEFT JOIN employees m ON m.employee_id = e.reporting_manager_id
        ORDER BY u.is_active DESC, u.app_role, u.full_name""")


class ManagerIn(BaseModel):
    """Promote an existing employee; a new title and level are optional."""
    employee_id: str
    start_date: date | None = None
    designation: str | None = Field(None, max_length=60)
    job_level: str | None = Field(None, pattern=r"^L[1-6]$")


@router.post("/managers")
def add_manager(body: ManagerIn, user=Depends(admin)):
    with conn() as c:
        old = c.execute("SELECT designation, job_level FROM employees WHERE employee_id = %s", (body.employee_id,)).fetchone()
        uid = _create_manager(c, user, body.employee_id, body.start_date or fetch_one("SELECT fd_as_of() AS d")["d"])
        if body.designation or body.job_level:
            c.execute("UPDATE employees SET designation = COALESCE(%s, designation), job_level = COALESCE(%s, job_level) WHERE employee_id = %s",
                      (body.designation, body.job_level, body.employee_id))
            _audit(c, "employee_promoted", user, "employee", body.employee_id, old=old,
                   new=dict(designation=body.designation, job_level=body.job_level))
    _reload()
    return dict(user_id=uid)


# ------------------------------------------------------------------ employees
class SkillIn(BaseModel):
    skill_id: str
    level: int = Field(ge=1, le=5)


class CertIn(BaseModel):
    cert_id: str
    issue_date: date
    expiry_date: date | None = None


class EmployeeIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=40)
    last_name: str = Field(min_length=1, max_length=40)
    designation: str = Field(min_length=2, max_length=60)
    job_level: str = Field(pattern=r"^L[1-6]$")
    role_family: str
    location: str
    work_mode: str = "Hybrid"
    date_of_joining: date
    prior_experience_years: float = Field(0, ge=0, le=40)
    reporting_manager_id: str
    gender: str | None = None                   # stored in the restricted schema, used only for fairness audits
    skills: list[SkillIn] = Field(min_length=1)
    certifications: list[CertIn] = []
    make_manager: bool = False                  # hiring a manager: the login is created in the same step


@router.post("/employees")
def add_employee(body: EmployeeIn, user=Depends(admin)):
    today = fetch_one("SELECT fd_as_of() AS d")["d"]
    names = state.rec.store.skill_name
    if any(s.skill_id not in names for s in body.skills):
        raise HTTPException(422, "Unknown skill")
    with conn() as c:
        c.execute("SELECT pg_advisory_xact_lock(4244)")
        practice = c.execute("SELECT practice FROM employees WHERE role_family = %s LIMIT 1", (body.role_family,)).fetchone()
        boss = c.execute("SELECT employment_status FROM employees WHERE employee_id = %s", (body.reporting_manager_id,)).fetchone()
        if not practice:
            raise HTTPException(422, "Unknown job family")
        if not boss or boss["employment_status"] == "Exited":
            raise HTTPException(422, "The reporting manager must be a current employee.")
        eid = f"NXT{c.execute('SELECT max(substr(employee_id, 4)::int) AS m FROM employees').fetchone()['m'] + 1}"
        base = re.sub(r"[^a-z]", "", body.first_name.lower()) + "." + re.sub(r"[^a-z]", "", body.last_name.lower())
        email, k = f"{base}@nexoratech.example", 1
        while c.execute("SELECT 1 FROM employees WHERE email = %s", (email,)).fetchone():
            k += 1
            email = f"{base}{k}@nexoratech.example"
        top = max(body.skills, key=lambda s: s.level)
        total = round(body.prior_experience_years + max(0, (today - body.date_of_joining).days) / 365.25, 1)
        full = f"{body.first_name.strip()} {body.last_name.strip()}"
        c.execute("""INSERT INTO employees (employee_id, first_name, last_name, full_name, email, designation, job_level, practice,
                         role_family, primary_skill, location, work_mode, date_of_joining, prior_experience_years,
                         total_experience_years, career_break_months, reporting_manager_id, employment_status)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,'Active')""",
                  (eid, body.first_name.strip(), body.last_name.strip(), full, email, body.designation, body.job_level,
                   practice["practice"], body.role_family, names[top.skill_id], body.location, body.work_mode,
                   body.date_of_joining, body.prior_experience_years, total, body.reporting_manager_id))
        acquired = min(body.date_of_joining, today)
        for s in {s.skill_id: s for s in body.skills}.values():
            c.execute("""INSERT INTO employee_skills (employee_id, skill_id, proficiency, proficiency_label, last_used_date,
                             is_manager_verified, acquired_on) VALUES (%s,%s,%s,%s,%s,false,%s)""",
                      (eid, s.skill_id, s.level, LABELS[s.level], today, acquired))
        n = c.execute("SELECT max(substr(employee_cert_id, 3)::int) AS m FROM employee_certifications").fetchone()["m"] or 0
        for i, cert in enumerate(body.certifications, start=1):
            c.execute("""INSERT INTO employee_certifications (employee_cert_id, employee_id, cert_id, issue_date, expiry_date,
                             verification_status) VALUES (%s,%s,%s,%s,%s,'Pending Verification')""",
                      (f"EC{n + i:05d}", eid, cert.cert_id, cert.issue_date, cert.expiry_date))
        if body.gender:
            c.execute("INSERT INTO restricted.employee_sensitive_attributes (employee_id, gender) VALUES (%s, %s)", (eid, body.gender))
        _audit(c, "employee_added", user, "employee", eid, name=full, reports_to=body.reporting_manager_id, skills=len(body.skills),
               hired_as_manager=body.make_manager)
        uid = _create_manager(c, user, eid, body.date_of_joining) if body.make_manager else None
    _reload()
    return dict(employee_id=eid, email=email, user_id=uid)


class ReportingIn(BaseModel):
    reporting_manager_id: str


@router.patch("/employees/{employee_id}/manager")
def change_manager(employee_id: str, body: ReportingIn, user=Depends(admin)):
    with conn() as c:
        e = c.execute("SELECT full_name, reporting_manager_id FROM employees WHERE employee_id = %s AND employment_status <> 'Exited'",
                      (employee_id,)).fetchone()
        if not e:
            raise HTTPException(404, "Employee not found")
        below = {r["employee_id"] for r in c.execute("""WITH RECURSIVE t AS (
                    SELECT employee_id FROM employees WHERE reporting_manager_id = %s
                    UNION SELECT x.employee_id FROM employees x JOIN t ON x.reporting_manager_id = t.employee_id)
                    SELECT employee_id FROM t""", (employee_id,)).fetchall()}
        if body.reporting_manager_id == employee_id or body.reporting_manager_id in below:
            raise HTTPException(409, "That would make someone report to a person below them.")
        if not c.execute("SELECT 1 FROM employees WHERE employee_id = %s AND employment_status <> 'Exited'", (body.reporting_manager_id,)).fetchone():
            raise HTTPException(404, "New manager not found")
        c.execute("UPDATE employees SET reporting_manager_id = %s WHERE employee_id = %s", (body.reporting_manager_id, employee_id))
        _audit(c, "reporting_changed", user, "employee", employee_id, old=e["reporting_manager_id"], new=body.reporting_manager_id)
    return dict(ok=True)


# ------------------------------------------------------------------ handover
def _handover_scope(c, old_user):
    """What a leaving manager is responsible for right now."""
    eid, uid = old_user["employee_id"], old_user["user_id"]
    q = lambda sql: c.execute(sql, {"e": eid, "u": uid}).fetchall()
    return dict(
        projects=q(f"SELECT project_id, project_name, status FROM projects WHERE project_manager_id = %(e)s AND status IN {OPEN} ORDER BY project_name"),
        delivery=q(f"SELECT project_id, project_name FROM projects WHERE delivery_manager_id = %(e)s AND status IN {OPEN} ORDER BY project_name"),
        reports=q("SELECT employee_id, full_name, designation FROM employees WHERE reporting_manager_id = %(e)s AND employment_status <> 'Exited' ORDER BY full_name"),
        approvals=q("""SELECT r.allocation_id, e.full_name AS employee, pr.role_title FROM allocation_approvals a
                       JOIN allocation_requests r USING (allocation_id) JOIN employees e USING (employee_id) JOIN project_roles pr USING (project_role_id)
                       WHERE a.approver_id = %(u)s AND a.status = 'pending' AND r.status = 'pending'"""),
        requests=q("""SELECT r.allocation_id, e.full_name AS employee, pr.role_title, r.status FROM allocation_requests r
                      JOIN employees e USING (employee_id) JOIN project_roles pr USING (project_role_id)
                      WHERE r.requested_by = %(u)s AND r.status IN ('pending', 'approved')"""),
        offers=q("SELECT suggestion_id FROM staffing_suggestions WHERE suggested_to = %(u)s AND status = 'new'"),
    )


def _leaving(c, user_id):
    u = c.execute("SELECT * FROM app_users WHERE user_id = %s AND app_role = 'manager' AND is_active", (user_id,)).fetchone()
    if not u:
        raise HTTPException(404, "Active manager not found")
    return u


@router.get("/handover/preview")
def handover_preview(from_user: str, to_employee: str, user=Depends(admin)):
    with conn() as c:
        old = _leaving(c, from_user)
        new = c.execute("SELECT employee_id, full_name, designation, employment_status FROM employees WHERE employee_id = %s", (to_employee,)).fetchone()
        if not new or new["employment_status"] != "Active":
            raise HTTPException(409, "The successor must be an active employee.")
        if new["employee_id"] == old["employee_id"]:
            raise HTTPException(409, "Choose someone other than the leaving manager.")
        has_login = c.execute("SELECT app_role FROM app_users WHERE employee_id = %s AND is_active", (to_employee,)).fetchone()
        if has_login and has_login["app_role"] != "manager":
            raise HTTPException(409, "The successor already has a non-manager login.")
        return dict(leaving=old["full_name"], successor=new["full_name"], successor_designation=new["designation"],
                    successor_is_manager=bool(has_login), **_handover_scope(c, old))


class HandoverIn(BaseModel):
    from_user: str
    to_employee: str
    end_date: date | None = None


@router.post("/handover")
def handover(body: HandoverIn, user=Depends(admin)):
    """Moves everything in one transaction, so nothing is left half-assigned."""
    today = fetch_one("SELECT fd_as_of() AS d")["d"]
    end = body.end_date or today
    handover_preview(body.from_user, body.to_employee, user)          # same checks as the preview
    with state.rec.lock, conn() as c:
        c.execute("SELECT pg_advisory_xact_lock(%s)", (decisions.DECISION_LOCK,))
        old = _leaving(c, body.from_user)
        scope = _handover_scope(c, old)
        new_e = body.to_employee
        row = c.execute("SELECT user_id FROM app_users WHERE employee_id = %s AND is_active", (new_e,)).fetchone()
        new_u = row["user_id"] if row else _create_manager(c, user, new_e, end)
        old_e, old_u = old["employee_id"], old["user_id"]

        c.execute(f"UPDATE projects SET project_manager_id = %s WHERE project_manager_id = %s AND status IN {OPEN}", (new_e, old_e))
        c.execute(f"UPDATE projects SET delivery_manager_id = %s WHERE delivery_manager_id = %s AND status IN {OPEN}", (new_e, old_e))
        # the successor takes the leaving manager's place in the chain, unless they already sit above them
        above = {r["employee_id"] for r in c.execute("""WITH RECURSIVE up AS (
                    SELECT reporting_manager_id AS employee_id FROM employees WHERE employee_id = %s
                    UNION SELECT e.reporting_manager_id FROM employees e JOIN up ON e.employee_id = up.employee_id
                    WHERE e.reporting_manager_id IS NOT NULL) SELECT employee_id FROM up""", (old_e,)).fetchall()}
        if new_e not in above:
            c.execute("UPDATE employees SET reporting_manager_id = (SELECT reporting_manager_id FROM employees WHERE employee_id = %s) WHERE employee_id = %s",
                      (old_e, new_e))
        c.execute("""UPDATE employees SET reporting_manager_id = %s
                     WHERE reporting_manager_id = %s AND employment_status <> 'Exited' AND employee_id <> %s""", (new_e, old_e, new_e))

        # open work: requests, approvals and offers follow the role, never leaving anyone to approve their own request
        c.execute("UPDATE allocation_requests SET requested_by = %s, updated_at = now() WHERE requested_by = %s AND status IN ('pending', 'approved')",
                  (new_u, old_u))
        c.execute("""UPDATE allocation_approvals a SET status = 'closed', comment = 'Handed over', decided_at = now()
                     WHERE a.approver_id = %s AND a.status = 'pending' AND EXISTS (
                       SELECT 1 FROM allocation_approvals b WHERE b.allocation_id = a.allocation_id AND b.approver_id = %s)""", (old_u, new_u))
        c.execute("UPDATE allocation_approvals SET approver_id = %s WHERE approver_id = %s AND status = 'pending'", (new_u, old_u))
        c.execute("""UPDATE allocation_approvals a SET status = 'closed', comment = 'Requester cannot approve', decided_at = now()
                     FROM allocation_requests r WHERE r.allocation_id = a.allocation_id AND a.approver_id = r.requested_by AND a.status = 'pending'""")
        c.execute("""UPDATE allocation_requests r SET status = 'approved', updated_at = now() WHERE r.status = 'pending'
                     AND NOT EXISTS (SELECT 1 FROM allocation_approvals a WHERE a.allocation_id = r.allocation_id AND a.status = 'pending')""")
        c.execute("UPDATE staffing_suggestions SET suggested_to = %s WHERE suggested_to = %s AND status = 'new'", (new_u, old_u))

        c.execute("UPDATE app_users SET is_active = false, end_date = %s WHERE user_id = %s", (end, old_u))
        c.execute("UPDATE employees SET employment_status = %s, exit_date = %s WHERE employee_id = %s",
                  ("Exited" if end <= today else "Serving Notice", end, old_e))
        counts = {k: len(v) for k, v in scope.items()}
        _audit(c, "manager_handover", user, "app_user", old_u, successor=new_e, successor_user=new_u, end_date=end, **counts)
    _reload()
    events.publish("allocation", dict(title=f"You now cover {old['full_name']}'s projects and team", users=[new_u], role_id=None))
    return dict(successor_user=new_u, **counts)
