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
        c.execute("DROP TABLE IF EXISTS baseline_role_status")
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
        c.execute("TRUNCATE notifications, assignment_decisions, recommendation_candidates, recommendation_requests, audit_log RESTART IDENTITY")
        n_asg = c.execute("DELETE FROM assignments WHERE assignment_id > %s", (b["baseline_assignment"],)).rowcount
        roles = "SELECT project_role_id FROM project_roles WHERE project_role_id > %s"
        c.execute(f"DELETE FROM project_role_skills WHERE project_role_id IN ({roles})", (b["baseline_role"],))
        c.execute(f"DELETE FROM project_role_certifications WHERE project_role_id IN ({roles})", (b["baseline_role"],))
        c.execute("DELETE FROM project_roles WHERE project_role_id > %s", (b["baseline_role"],))
        c.execute("DELETE FROM project_embeddings WHERE project_id > %s", (b["baseline_project"],))
        n_prj = c.execute("DELETE FROM projects WHERE project_id > %s", (b["baseline_project"],)).rowcount
        c.execute("""UPDATE project_roles r SET demand_status = b.demand_status FROM baseline_role_status b
                     WHERE b.project_role_id = r.project_role_id AND r.demand_status <> b.demand_status""")
    for method, url in (("DELETE", "http://localhost:8025/api/v1/messages"),    # empty the Mailpit inbox
                        ("POST", "http://localhost:8000/api/admin/reload")):    # tell a running API to reload
        try:
            httpx.request(method, url, timeout=10)
        except httpx.HTTPError:
            pass
    print(f"reset done: removed {n_asg} assignment(s), {n_prj} project(s), all decisions, notifications and emails.")


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
