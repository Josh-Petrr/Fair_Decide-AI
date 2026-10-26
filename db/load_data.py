"""Rebuild the FairDecide database and bulk-load the generated CSVs.

Run from the project root:   .venv\\Scripts\\python -m db.load_data
Connection string comes from DATABASE_URL (.env), defaulting to the local docker-compose database.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# (table, csv file) in foreign-key order
LOAD_ORDER = [
    ("skills", "skills"),
    ("skill_aliases", "skill_aliases"),
    ("certifications", "certifications"),
    ("certification_skills", "certification_skills"),
    ("policies", "policies"),
    ("employees", "employees"),
    ("restricted.employee_sensitive_attributes", "employee_sensitive_attributes"),
    ("employee_skills", "employee_skills"),
    ("employee_certifications", "employee_certifications"),
    ("employee_leaves", "employee_leaves"),
    ("clients", "clients"),
    ("projects", "projects"),
    ("project_roles", "project_roles"),
    ("project_role_skills", "project_role_skills"),
    ("project_role_certifications", "project_role_certifications"),
    ("assignments", "assignments"),
    ("assignment_feedback", "assignment_feedback"),
    ("app_users", "app_users"),
]


def main():
    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL", "postgresql://fairdecide:fairdecide_dev@localhost:5432/fairdecide")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
            for table, name in LOAD_ORDER:
                path = DATA / f"{name}.csv"
                header = path.open(encoding="utf-8").readline().strip()
                with cur.copy(f"COPY {table} ({header}) FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
                    copy.write(path.read_bytes())
                cur.execute(f"SELECT count(*) FROM {table}")
                print(f"  {table:45s} {cur.fetchone()[0]:>7,}")
        conn.commit()
    print("Load complete.")


if __name__ == "__main__":
    main()
