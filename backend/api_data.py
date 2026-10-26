"""Read/write endpoints for users, dashboard, projects, demands, employees and the audit trail."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import state
from .auth import current_user, make_token, manager
from .db import conn, fetch_all, fetch_one
from .engine.embeddings import embed, project_text, to_pg

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------ auth
class Login(BaseModel):
    user_id: str


@router.get("/auth/users")
def demo_users():
    return fetch_all("""SELECT u.user_id, u.full_name, u.app_role, e.designation, e.location
                        FROM app_users u LEFT JOIN employees e USING (employee_id)
                        WHERE u.is_active ORDER BY u.app_role, u.full_name""")


@router.post("/auth/login")
def login(body: Login):
    user = fetch_one("SELECT user_id, full_name, app_role, employee_id FROM app_users WHERE user_id = %s AND is_active",
                     (body.user_id,))
    if not user:
        raise HTTPException(404, "User not found")
    return dict(token=make_token(user["user_id"]), user=user)


@router.get("/auth/me")
def me(user=Depends(current_user)):
    return user


# ------------------------------------------------------------------ reference data for forms
@router.get("/meta")
def meta(user=Depends(current_user)):
    return dict(
        as_of=fetch_one("SELECT fd_as_of() AS d")["d"],
        skills=fetch_all("SELECT skill_id, skill_name, category FROM skills ORDER BY category, skill_name"),
        certifications=fetch_all("SELECT cert_id, cert_name, vendor FROM certifications WHERE retired_on IS NULL ORDER BY vendor, cert_name"),
        clients=fetch_all("SELECT client_id, client_name, industry FROM clients ORDER BY client_name"),
        families=fetch_all("SELECT DISTINCT role_family, practice FROM employees ORDER BY practice"),
        locations=[r["location"] for r in fetch_all("SELECT DISTINCT location FROM employees ORDER BY 1")],
    )


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard")
def dashboard(user=Depends(current_user)):
    kpi = fetch_one("""
        SELECT (SELECT count(*) FROM employees WHERE employment_status <> 'Exited') AS headcount,
               (SELECT count(*) FROM v_employee_current_load l JOIN employees e USING (employee_id)
                 WHERE l.current_allocation_pct = 0 AND e.employment_status = 'Active') AS bench,
               (SELECT count(*) FROM v_employee_current_load WHERE current_allocation_pct > 100) AS overallocated,
               (SELECT count(*) FROM v_employee_current_load WHERE active_project_count >= 2) AS multi_project,
               (SELECT count(*) FROM projects WHERE status = 'Active') AS active_projects,
               (SELECT count(*) FROM projects WHERE status = 'Pipeline') AS pipeline_projects,
               (SELECT count(*) FROM v_open_demands) AS open_demands,
               (SELECT COALESCE(sum(headcount), 0) FROM v_open_demands) AS open_positions,
               (SELECT round(avg(LEAST(current_allocation_pct, 100))) FROM v_employee_current_load) AS utilisation""")
    by_practice = fetch_all("""
        SELECT e.practice, count(*) AS people, round(avg(LEAST(l.current_allocation_pct, 100))) AS utilisation,
               count(*) FILTER (WHERE l.current_allocation_pct = 0) AS bench,
               count(*) FILTER (WHERE l.current_allocation_pct > 100) AS overallocated
        FROM employees e JOIN v_employee_current_load l USING (employee_id)
        WHERE e.employment_status = 'Active' GROUP BY e.practice ORDER BY people DESC""")
    rolloffs = fetch_all("""
        SELECT a.employee_id, e.full_name, e.designation, p.project_name, a.end_date, a.allocation_pct
        FROM assignments a JOIN employees e USING (employee_id) JOIN projects p USING (project_id)
        WHERE a.status = 'Active' AND a.end_date BETWEEN fd_as_of() AND fd_as_of() + 30
        ORDER BY a.end_date LIMIT 8""")
    urgent = fetch_all("""
        SELECT d.project_role_id, d.role_title, d.project_name, d.start_date, d.headcount, d.priority, c.client_name
        FROM v_open_demands d JOIN clients c USING (client_id)
        ORDER BY d.start_date, CASE d.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END LIMIT 8""")
    return dict(kpi=kpi, by_practice=by_practice, rolloffs=rolloffs, urgent_demands=urgent,
                recent_decisions=audit_list(limit=6, user=user))


# ------------------------------------------------------------------ projects
@router.get("/projects")
def projects(status: str | None = None, q: str | None = None, user=Depends(current_user)):
    return fetch_all("""
        SELECT p.project_id, p.project_code, p.project_name, c.client_name, p.industry, p.project_type, p.status,
               p.priority, p.start_date, p.end_date, p.delivery_location,
               (SELECT count(*) FROM v_open_demands d WHERE d.project_id = p.project_id) AS open_demands,
               (SELECT count(DISTINCT employee_id) FROM assignments a WHERE a.project_id = p.project_id
                  AND a.status IN ('Active', 'Upcoming')) AS team_size
        FROM projects p JOIN clients c USING (client_id)
        WHERE (%(s)s::text IS NULL OR p.status = %(s)s) AND (%(q)s::text IS NULL OR p.project_name ILIKE %(q)s
               OR c.client_name ILIKE %(q)s OR p.project_code ILIKE %(q)s)
        ORDER BY CASE p.status WHEN 'Pipeline' THEN 0 WHEN 'Active' THEN 1 ELSE 2 END, p.start_date DESC LIMIT 200""",
                     dict(s=status, q=f"%{q}%" if q else None))


@router.get("/projects/{project_id}")
def project_detail(project_id: str, user=Depends(current_user)):
    p = fetch_one("""SELECT p.*, c.client_name, c.country, pm.full_name AS project_manager
                     FROM projects p JOIN clients c USING (client_id)
                     LEFT JOIN employees pm ON pm.employee_id = p.project_manager_id WHERE p.project_id = %s""", (project_id,))
    if not p:
        raise HTTPException(404, "Project not found")
    roles = fetch_all("""
        SELECT r.*, (SELECT json_agg(json_build_object('skill', s.skill_name, 'min', rs.min_proficiency, 'importance', rs.importance))
                     FROM project_role_skills rs JOIN skills s USING (skill_id) WHERE rs.project_role_id = r.project_role_id) AS skills,
               (SELECT json_agg(json_build_object('employee_id', a.employee_id, 'name', e.full_name, 'status', a.status,
                                                  'start', a.start_date, 'end', a.end_date, 'allocation', a.allocation_pct))
                FROM assignments a JOIN employees e USING (employee_id) WHERE a.project_role_id = r.project_role_id) AS people
        FROM project_roles r WHERE r.project_id = %s ORDER BY r.start_date, r.role_title""", (project_id,))
    return dict(project=p, roles=roles)


class SkillReq(BaseModel):
    skill_id: str
    min_level: int = Field(3, ge=1, le=5)


class RoleIn(BaseModel):
    title: str
    family: str
    headcount: int = Field(1, ge=1, le=20)
    min_experience: float = Field(0, ge=0, le=30)
    allocation: int = Field(100, ge=10, le=100)
    start_date: date | None = None
    end_date: date | None = None
    mandatory_skills: list[SkillReq]
    preferred_skills: list[str] = []
    mandatory_certs: list[str] = []
    preferred_certs: list[str] = []


class ProjectIn(BaseModel):
    project_name: str = Field(min_length=3)
    client_id: str
    description: str = Field(min_length=10)
    project_type: str = "New Development"
    engagement_model: str = "Time & Material"
    priority: str = "High"
    delivery_location: str = "Bengaluru"
    start_date: date
    end_date: date
    roles: list[RoleIn] = Field(min_length=1)


@router.post("/projects")
def create_project(body: ProjectIn, user=Depends(manager)):
    if body.end_date <= body.start_date:
        raise HTTPException(422, "End date must be after the start date")
    client = fetch_one("SELECT * FROM clients WHERE client_id = %s", (body.client_id,))
    if not client:
        raise HTTPException(422, "Unknown client")
    today = fetch_one("SELECT fd_as_of() AS d")["d"]
    with conn() as c:
        c.execute("SELECT pg_advisory_xact_lock(4243)")
        n = c.execute("SELECT max(substr(project_id, 4)::int) AS m FROM projects").fetchone()["m"] + 1
        pid = f"PRJ{n:04d}"
        seq = c.execute("SELECT count(*) AS k FROM projects WHERE client_id = %s AND extract(year FROM start_date) = %s",
                        (body.client_id, body.start_date.year)).fetchone()["k"] + 1
        code = f"{body.client_id}-{str(body.start_date.year)[2:]}-{seq:02d}N"
        stack = ", ".join(dict.fromkeys(s for r in body.roles for s in
                                        (state.rec.store.skill_name[x.skill_id] for x in r.mandatory_skills)))
        c.execute("""INSERT INTO projects (project_id, project_code, project_name, client_id, industry, project_type,
                         engagement_model, description, tech_stack, start_date, end_date, status, priority,
                         delivery_location, project_manager_id, delivery_manager_id, planned_team_size, created_on)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (pid, code, body.project_name, body.client_id, client["industry"], body.project_type,
                   body.engagement_model, body.description, stack, body.start_date, body.end_date,
                   "Pipeline" if body.start_date > today else "Active", body.priority, body.delivery_location,
                   user["employee_id"], client["account_delivery_manager_id"], sum(r.headcount for r in body.roles), today))
        m = c.execute("SELECT max(substr(project_role_id, 3)::int) AS m FROM project_roles").fetchone()["m"]
        role_ids = []
        for k, r in enumerate(body.roles, start=1):
            rid = f"PR{m + k:05d}"
            role_ids.append(rid)
            c.execute("""INSERT INTO project_roles (project_role_id, project_id, role_title, role_family, headcount,
                             min_experience_years, allocation_pct, start_date, end_date, demand_type, demand_status, created_on)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Initial','Open',%s)""",
                      (rid, pid, r.title, r.family, r.headcount, r.min_experience, r.allocation,
                       r.start_date or body.start_date, r.end_date or body.end_date, today))
            must = {s.skill_id: s.min_level for s in r.mandatory_skills}
            for sid, lvl in must.items():
                c.execute("INSERT INTO project_role_skills VALUES (%s,%s,%s,'Mandatory')", (rid, sid, lvl))
            for sid in dict.fromkeys(r.preferred_skills):
                if sid not in must:
                    c.execute("INSERT INTO project_role_skills VALUES (%s,%s,NULL,'Preferred')", (rid, sid))
            for cid in dict.fromkeys(r.mandatory_certs):
                c.execute("INSERT INTO project_role_certifications VALUES (%s,%s,'Mandatory')", (rid, cid))
            for cid in dict.fromkeys(r.preferred_certs):
                if cid not in r.mandatory_certs:
                    c.execute("INSERT INTO project_role_certifications VALUES (%s,%s,'Preferred')", (rid, cid))
        text = project_text(dict(project_name=body.project_name, industry=client["industry"], project_type=body.project_type,
                                 description=body.description, tech_stack=stack))
        c.execute("INSERT INTO project_embeddings VALUES (%s, 'sentence-transformers/all-MiniLM-L6-v2', %s, %s::vector)",
                  (pid, text, to_pg(embed([text])[0])))
        c.execute("INSERT INTO audit_log (event_type, actor, entity, entity_id, payload) VALUES "
                  "('project_created', %s, 'project', %s, jsonb_build_object('roles', %s::int))",
                  (user["user_id"], pid, len(role_ids)))
    with state.rec.lock:
        state.rec.store.load_static()
        state.rec.store.refresh()
    return dict(project_id=pid, project_code=code, role_ids=role_ids)


# ------------------------------------------------------------------ demands
@router.get("/demands")
def demands(user=Depends(current_user)):
    return fetch_all("""
        SELECT d.project_role_id, d.role_title, d.role_family, d.headcount, d.allocation_pct, d.min_experience_years,
               d.start_date, d.end_date, d.demand_type, d.demand_status, d.project_id, d.project_name, d.priority,
               d.project_status, c.client_name,
               (SELECT count(*) FROM assignments a WHERE a.project_role_id = d.project_role_id
                  AND a.status IN ('Active', 'Upcoming')) AS filled,
               (SELECT string_agg(s.skill_name, ', ') FROM project_role_skills rs JOIN skills s USING (skill_id)
                 WHERE rs.project_role_id = d.project_role_id AND rs.importance = 'Mandatory') AS skills
        FROM v_open_demands d JOIN clients c USING (client_id)
        ORDER BY d.start_date, d.project_name""")


# ------------------------------------------------------------------ employees
@router.get("/employees")
def employees(q: str | None = None, practice: str | None = None, available: bool = False, user=Depends(current_user)):
    return fetch_all("""
        SELECT e.employee_id, e.full_name, e.designation, e.job_level, e.practice, e.primary_skill, e.location,
               e.employment_status, e.total_experience_years, l.current_allocation_pct, l.active_project_count
        FROM employees e JOIN v_employee_current_load l USING (employee_id)
        WHERE (%(q)s::text IS NULL OR e.full_name ILIKE %(q)s OR e.employee_id ILIKE %(q)s OR e.primary_skill ILIKE %(q)s
               OR EXISTS (SELECT 1 FROM employee_skills es JOIN skills s USING (skill_id)
                          WHERE es.employee_id = e.employee_id AND s.skill_name ILIKE %(q)s))
          AND (%(p)s::text IS NULL OR e.practice = %(p)s)
          AND (NOT %(a)s OR (e.employment_status = 'Active' AND l.current_allocation_pct < 100))
        ORDER BY l.current_allocation_pct, e.full_name LIMIT 100""",
                     dict(q=f"%{q}%" if q else None, p=practice, a=available))


@router.get("/employees/{employee_id}")
def employee_profile(employee_id: str, user=Depends(current_user)):
    e = fetch_one("""SELECT e.*, m.full_name AS manager_name, l.current_allocation_pct, l.active_project_count
                     FROM employees e LEFT JOIN employees m ON m.employee_id = e.reporting_manager_id
                     LEFT JOIN v_employee_current_load l ON l.employee_id = e.employee_id
                     WHERE e.employee_id = %s""", (employee_id,))
    if not e:
        raise HTTPException(404, "Employee not found")
    skills = fetch_all("""SELECT s.skill_name, s.category, es.proficiency, es.years_used, es.last_used_date,
                                 es.is_manager_verified, es.acquired_on,
                                 EXISTS (SELECT 1 FROM assignments a JOIN project_role_skills rs USING (project_role_id)
                                         WHERE a.employee_id = es.employee_id AND rs.skill_id = es.skill_id
                                           AND a.start_date <= fd_as_of()) AS proven_on_project
                          FROM employee_skills es JOIN skills s USING (skill_id)
                          WHERE es.employee_id = %s ORDER BY es.proficiency DESC NULLS LAST, s.skill_name""", (employee_id,))
    certs = fetch_all("""SELECT cert_name, vendor, credential_id, issue_date, expiry_date, is_valid, has_date_error
                         FROM v_employee_certification_status WHERE employee_id = %s ORDER BY issue_date DESC""", (employee_id,))
    history = fetch_all("""SELECT a.assignment_id, a.project_id, p.project_name, c.client_name, p.industry, a.role_title,
                                  a.allocation_pct, a.start_date, a.end_date, a.status, a.performance_rating, a.release_reason,
                                  f.comments AS feedback
                           FROM assignments a JOIN projects p USING (project_id) JOIN clients c ON c.client_id = p.client_id
                           LEFT JOIN assignment_feedback f USING (assignment_id)
                           WHERE a.employee_id = %s ORDER BY a.start_date DESC""", (employee_id,))
    leaves = fetch_all("SELECT leave_type, start_date, end_date, status FROM employee_leaves WHERE employee_id = %s "
                       "AND end_date >= fd_as_of() ORDER BY start_date", (employee_id,))
    return dict(employee=e, skills=skills, certifications=certs, assignments=history, leaves=leaves)


# ------------------------------------------------------------------ audit trail & notifications
@router.get("/audit")
def audit_list(limit: int = 50, user=Depends(current_user)):
    return fetch_all("""
        SELECT d.decision_id, d.decided_at, d.decision, d.decision_reason, d.notes, d.selected_employee_ids,
               u.full_name AS decided_by, r.role_title, p.project_name, p.project_id, d.request_id,
               (SELECT json_agg(json_build_object('name', e.full_name, 'status', n.status, 'recipient', n.recipient))
                FROM notifications n JOIN employees e USING (employee_id) WHERE n.decision_id = d.decision_id) AS notifications
        FROM assignment_decisions d JOIN app_users u ON u.user_id = d.decided_by
        JOIN project_roles r USING (project_role_id) JOIN projects p USING (project_id)
        ORDER BY d.decided_at DESC LIMIT %s""", (limit,))


@router.get("/audit/{decision_id}")
def audit_detail(decision_id: int, user=Depends(current_user)):
    d = fetch_one("SELECT * FROM assignment_decisions WHERE decision_id = %s", (decision_id,))
    if not d:
        raise HTTPException(404, "Decision not found")
    req = fetch_one("SELECT * FROM recommendation_requests WHERE request_id = %s", (d["request_id"],)) if d["request_id"] else None
    cands = fetch_all("""SELECT rc.*, e.full_name FROM recommendation_candidates rc JOIN employees e USING (employee_id)
                         WHERE rc.request_id = %s ORDER BY rc.rank""", (d["request_id"],)) if d["request_id"] else []
    notes = fetch_all("SELECT * FROM notifications WHERE decision_id = %s", (decision_id,))
    return dict(decision=d, request=req, candidates=cands, notifications=notes)
