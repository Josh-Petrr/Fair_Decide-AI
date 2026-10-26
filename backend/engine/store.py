"""In-memory snapshot of everything the matching engine needs (loaded once, refreshed after changes).

Dates are kept as integer ordinals (date.toordinal()) so comparisons are cheap.
"""
from collections import defaultdict
from datetime import date

import numpy as np

from ..db import fetch_all

PROTECTED = ("gender", "date_of_birth", "age_band", "career_break_months")   # never used as features


def _o(d):
    return d.toordinal() if d else None


class Store:
    def __init__(self):
        self.load_static()
        self.load_dynamic()

    # ---------------------------------------------------------------- slow-changing reference data
    def load_static(self):
        self.skill_name = {r["skill_id"]: r["skill_name"] for r in fetch_all("SELECT skill_id, skill_name FROM skills")}
        self.skill_id = {v.lower(): k for k, v in self.skill_name.items()}
        self.cert_name = {r["cert_id"]: r["cert_name"] for r in fetch_all("SELECT cert_id, cert_name FROM certifications")}
        self.policy = {r["rule_key"]: r["rule_value"] for r in fetch_all("SELECT rule_key, rule_value FROM policies")}

        self.emp = {}
        for r in fetch_all("""SELECT employee_id, full_name, email, designation, job_level, role_family, practice,
                                     primary_skill, location, date_of_joining, prior_experience_years,
                                     total_experience_years, employment_status, exit_date, last_appraisal_rating
                              FROM employees"""):
            r["level"] = int(r["job_level"][1])
            r["join"] = _o(r["date_of_joining"])
            r["exit"] = _o(r["exit_date"])
            r["prior_exp"] = float(r["prior_experience_years"] or 0)
            self.emp[r["employee_id"]] = r

        self.skills = defaultdict(list)     # emp -> [(skill_id, prof|None, acquired_ord, verified, years_used)]
        for r in fetch_all("SELECT employee_id, skill_id, proficiency, acquired_on, is_manager_verified, years_used FROM employee_skills"):
            self.skills[r["employee_id"]].append((r["skill_id"], r["proficiency"], _o(r["acquired_on"]),
                                                  r["is_manager_verified"], float(r["years_used"] or 0)))
        self.certs = defaultdict(list)      # emp -> [(cert_id, issue_ord, expiry_ord|None)]
        for r in fetch_all("SELECT employee_id, cert_id, issue_date, expiry_date FROM employee_certifications"):
            self.certs[r["employee_id"]].append((r["cert_id"], _o(r["issue_date"]), _o(r["expiry_date"])))
        self.leaves = defaultdict(list)     # emp -> [(start, end)] approved leave > 10 days
        for r in fetch_all("SELECT employee_id, start_date, end_date FROM employee_leaves "
                           "WHERE status = 'Approved' AND end_date - start_date > 10"):
            self.leaves[r["employee_id"]].append((_o(r["start_date"]), _o(r["end_date"])))

        emb = fetch_all("SELECT project_id, embedding::text AS v FROM project_embeddings")
        self.proj_index = {r["project_id"]: i for i, r in enumerate(emb)}
        self.proj_vecs = np.array([np.fromstring(r["v"][1:-1], sep=",") for r in emb], dtype=np.float32)

    # ---------------------------------------------------------------- data that changes when managers act
    def load_dynamic(self):
        self.projects = {r["project_id"]: r for r in fetch_all(
            """SELECT p.project_id, p.project_name, p.client_id, c.client_name, p.industry, p.status, p.priority,
                      p.description, p.start_date, p.end_date
               FROM projects p JOIN clients c USING (client_id)""")}
        self.roles = {}
        for r in fetch_all("""SELECT project_role_id, project_id, role_title, role_family, headcount, min_experience_years,
                                     allocation_pct, start_date, end_date, demand_status FROM project_roles"""):
            r.update(must=[], nice=[], mcerts=[], pcerts=[])
            self.roles[r["project_role_id"]] = r
        for r in fetch_all("SELECT project_role_id, skill_id, min_proficiency, importance FROM project_role_skills"):
            role = self.roles[r["project_role_id"]]
            if r["importance"] == "Mandatory":
                role["must"].append((r["skill_id"], r["min_proficiency"] or 3))
            else:
                role["nice"].append(r["skill_id"])
        for r in fetch_all("SELECT project_role_id, cert_id, importance FROM project_role_certifications"):
            self.roles[r["project_role_id"]]["mcerts" if r["importance"] == "Mandatory" else "pcerts"].append(r["cert_id"])

        self.asg = fetch_all("""SELECT assignment_id, employee_id, project_id, project_role_id, allocation_pct,
                                       start_date, end_date, status, performance_rating
                                FROM assignments WHERE status <> 'Cancelled'""")
        adjusted = {r["assignment_id"]: float(r["adjusted_rating"])
                    for r in fetch_all("SELECT assignment_id, adjusted_rating FROM rating_adjustments")}
        self.asg_by_emp = defaultdict(list)
        for a in self.asg:
            a["rating_adj"] = adjusted.get(a["assignment_id"], a["performance_rating"])
            a["s"], a["e"] = _o(a["start_date"]), _o(a["end_date"])
            a["industry"] = self.projects[a["project_id"]]["industry"]
            role = self.roles.get(a["project_role_id"])
            a["skills_used"] = {s for s, _ in role["must"]} | set(role["nice"]) if role else set()
            self.asg_by_emp[a["employee_id"]].append(a)

    def refresh(self):
        self.load_dynamic()

    # ---------------------------------------------------------------- helpers
    def role_spec(self, role_id):
        """Turn a stored demand into the dict the engine works with."""
        r = self.roles[role_id]
        p = self.projects[r["project_id"]]
        i = self.proj_index.get(r["project_id"])
        return dict(role_id=role_id, project_id=r["project_id"], title=r["role_title"], family=r["role_family"],
                    industry=p["industry"], min_exp=float(r["min_experience_years"] or 0), alloc=r["allocation_pct"],
                    headcount=r["headcount"], start=_o(r["start_date"]), end=_o(r["end_date"]),
                    must=list(r["must"]), nice=list(r["nice"]), mcerts=list(r["mcerts"]), pcerts=list(r["pcerts"]),
                    embedding=self.proj_vecs[i] if i is not None else None)

    def load_on(self, emp_id, day, exclude=None):
        """Allocation % and number of projects on a given day."""
        live = [a for a in self.asg_by_emp[emp_id] if a["s"] <= day <= a["e"] and a["assignment_id"] != exclude]
        return sum(a["allocation_pct"] for a in live), len({a["project_id"] for a in live})


def today_ordinal():
    from ..db import as_of
    return as_of().toordinal()


def from_ordinal(o):
    return date.fromordinal(o) if o else None
