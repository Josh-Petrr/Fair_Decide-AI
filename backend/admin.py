"""Admin commands.

  .venv\\Scripts\\python -m backend.admin setup   full build: generate data -> load DB -> embeddings -> ML pipeline (~2 min)
  .venv\\Scripts\\python -m backend.admin reset   undo everything done in the app since setup (seconds) - use before a demo
"""
import sys

import httpx
import pandas as pd

from .config import ROOT
from .db import conn, fetch_one

DATA = ROOT / "data"

BASELINE_KEYS = ("baseline_assignment", "baseline_project", "baseline_role")


def snapshot():
    """Remember where the generated data ends (from the CSVs), so reset removes only what the app added."""
    roles = pd.read_csv(DATA / "project_roles.csv", usecols=["project_role_id", "demand_status"])
    b = dict(baseline_assignment=pd.read_csv(DATA / "assignments.csv", usecols=["assignment_id"]).assignment_id.max(),
             baseline_project=pd.read_csv(DATA / "projects.csv", usecols=["project_id"]).project_id.max(),
             baseline_role=roles.project_role_id.max())
    with conn() as c:
        c.execute("DROP TABLE IF EXISTS baseline_role_status, baseline_reporting, baseline_people, baseline_projects, baseline_users")
        tables = {   # what the app can change, as generated
            "baseline_people": ("employees", ["employee_id", "reporting_manager_id", "employment_status", "exit_date", "designation", "job_level"]),
            "baseline_projects": ("projects", ["project_id", "project_manager_id", "delivery_manager_id"]),
            "baseline_users": ("app_users", ["user_id", "employee_id", "app_role", "is_active", "start_date", "end_date"]),
        }
        for name, (src, cols) in tables.items():
            c.execute(f"CREATE TABLE {name} AS SELECT {', '.join(cols)} FROM {src} WITH NO DATA")
            df = pd.read_csv(DATA / f"{src}.csv", usecols=cols, dtype=str)[cols]
            with c.cursor().copy(f"COPY {name} ({', '.join(cols)}) FROM STDIN") as cp:
                for r in df.itertuples(index=False):
                    cp.write_row([None if pd.isna(v) else v for v in r])
        c.execute("CREATE TABLE baseline_role_status (project_role_id text PRIMARY KEY, demand_status text)")
        with c.cursor().copy("COPY baseline_role_status FROM STDIN") as cp:
            for r in roles.itertuples(index=False):
                cp.write_row(r)
        for k in BASELINE_KEYS:
            c.execute("INSERT INTO app_settings VALUES (%s, %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value",
                      (k, b[k]))
    print("baseline saved:", dict(b))


def reset():
    b = {k: fetch_one("SELECT setting_value FROM app_settings WHERE setting_key = %s", (k,))["setting_value"] for k in BASELINE_KEYS}
    with conn() as c:
        # app-written logs (TRUNCATE bypasses the append-only triggers, which guard DELETE/UPDATE)
        c.execute("TRUNCATE staffing_suggestions, allocation_approvals, allocation_requests, notifications, assignment_decisions, recommendation_candidates, recommendation_requests, audit_log RESTART IDENTITY")
        n_asg = c.execute("DELETE FROM assignments WHERE assignment_id > %s", (b["baseline_assignment"],)).rowcount
        roles = "SELECT project_role_id FROM project_roles WHERE project_role_id > %s"
        c.execute(f"DELETE FROM project_role_skills WHERE project_role_id IN ({roles})", (b["baseline_role"],))
        c.execute(f"DELETE FROM project_role_certifications WHERE project_role_id IN ({roles})", (b["baseline_role"],))
        c.execute("DELETE FROM project_roles WHERE project_role_id > %s", (b["baseline_role"],))
        c.execute("DELETE FROM project_embeddings WHERE project_id > %s", (b["baseline_project"],))
        n_prj = c.execute("DELETE FROM projects WHERE project_id > %s", (b["baseline_project"],)).rowcount
        c.execute("""UPDATE project_roles r SET demand_status = b.demand_status FROM baseline_role_status b
                     WHERE b.project_role_id = r.project_role_id AND r.demand_status <> b.demand_status""")
        # admin changes: logins, project heads, reporting lines, leavers and added employees
        n_usr = c.execute("DELETE FROM app_users WHERE user_id NOT IN (SELECT user_id FROM baseline_users)").rowcount
        c.execute("""UPDATE app_users u SET employee_id = b.employee_id, app_role = b.app_role, is_active = b.is_active,
                     start_date = b.start_date, end_date = b.end_date FROM baseline_users b WHERE b.user_id = u.user_id""")
        c.execute("""UPDATE projects p SET project_manager_id = b.project_manager_id, delivery_manager_id = b.delivery_manager_id
                     FROM baseline_projects b WHERE b.project_id = p.project_id""")
        c.execute("""UPDATE employees e SET reporting_manager_id = b.reporting_manager_id, employment_status = b.employment_status,
                     exit_date = b.exit_date, designation = b.designation, job_level = b.job_level
                     FROM baseline_people b WHERE b.employee_id = e.employee_id
                     AND (e.reporting_manager_id, e.employment_status, e.exit_date, e.designation, e.job_level) IS DISTINCT FROM
                         (b.reporting_manager_id, b.employment_status, b.exit_date, b.designation, b.job_level)""")
        added = "SELECT employee_id FROM employees WHERE employee_id NOT IN (SELECT employee_id FROM baseline_people)"
        for t in ("employee_skills", "employee_certifications", "employee_leaves", "employee_profile_embeddings",
                  "restricted.employee_sensitive_attributes"):
            c.execute(f"DELETE FROM {t} WHERE employee_id IN ({added})")
        n_emp = c.execute(f"DELETE FROM employees WHERE employee_id IN ({added})").rowcount
    for method, url in (("DELETE", "http://localhost:8025/api/v1/messages"),    # empty the Mailpit inbox
                        ("POST", "http://localhost:8000/api/admin/reload")):    # tell a running API to reload
        try:
            httpx.request(method, url, timeout=10)
        except httpx.HTTPError:
            pass
    print(f"reset done: removed {n_asg} assignment(s), {n_prj} project(s), {n_emp} added employee(s), {n_usr} added login(s); "
          "restored managers and project heads; cleared all decisions, notifications and emails.")


def setup():
    from datagen import generate
    from db import load_data
    from .engine import embeddings
    from .ml import pipeline
    generate.main()
    load_data.main()
    embeddings.build_all()
    pipeline.run()
    snapshot()
    reset()          # clears logs/mailbox and makes a running API reload


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"setup": setup, "reset": reset, "snapshot": snapshot}.get(cmd, lambda: print(__doc__))()
