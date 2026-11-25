"""Live recommendations: filter -> score -> explain -> flag -> audit. Pure computation, no database writes."""
import json
import threading
import warnings

import joblib
import lightgbm as lgb
import numpy as np
import shap

from ..config import ARTIFACTS
from ..db import fetch_all
from ..ml.train import apply_calibrator
from . import features, filters
from .store import Store, from_ordinal, today_ordinal

# Feature -> human factor group (SHAP values are summed per group for a readable explanation)
GROUPS = {
    "Skill match": ["must_coverage", "must_held", "must_gap", "must_surplus", "must_unknown", "nice_coverage"],
    "Experience": ["exp_years", "exp_gap", "level"],
    "Relevant projects": ["domain_projects", "sim_max", "sim_top3", "same_family", "total_projects"],
    "Past performance": ["past_rating"],
    "Certifications": ["mcert_ok", "pcert_count"],
    "Skill evidence": ["verified_share", "evidenced_share"],
    "Workload": ["load_before", "load_after", "concurrent", "overloaded", "alloc"],
}


warnings.filterwarnings("ignore", message="LightGBM binary classifier with TreeExplainer")

REASON_CATEGORIES = [("Missing", "Missing mandatory skill"), ("level not recorded", "Skill level not recorded"),
                     ("/5 (needs", "Skill level too low"), ("not valid on start", "Certification not valid"),
                     ("yrs experience", "Not enough experience"), ("Would be at", "No capacity on start date"),
                     ("Already on", "Already on this / max projects"), ("Serving notice", "Serving notice"),
                     ("leave", "On leave"), ("induction", "In induction")]


def reason_category(reason):
    return next((label for key, label in REASON_CATEGORIES if key in reason), "Other")


class Recommender:
    def __init__(self):
        self.lock = threading.RLock()
        self.store = Store()
        self.model = lgb.Booster(model_file=str(ARTIFACTS / "suitability_lgbm.txt"))
        self.cal = joblib.load(ARTIFACTS / "calibrator.joblib")
        self.meta = json.loads((ARTIFACTS / "model_meta.json").read_text())
        self.feats = self.meta["features"]
        self.explainer = shap.TreeExplainer(self.model)
        self.gender = {r["employee_id"]: r["gender"]       # audit only - never passed to the model
                       for r in fetch_all("SELECT employee_id, gender FROM restricted.employee_sensitive_attributes")}

    def refresh(self):
        with self.lock:
            self.store.refresh()

    # ------------------------------------------------------------------ main entry point
    def recommend(self, role, top_n=10):
        st, today = self.store, today_ordinal()
        eligible, excluded, warn = [], [], {}
        for eid, e in st.emp.items():
            if e["employment_status"] == "Exited":
                continue
            blockers, warnings = filters.check(st, role, eid, today)
            if blockers:
                excluded.append((eid, blockers))
            else:
                eligible.append(eid)
                warn[eid] = warnings

        ranked = self._score(role, eligible, today)
        top = ranked[:top_n]
        candidates = [self._card(role, r, today, warn[r["employee_id"]], rank=i + 1) for i, r in enumerate(top)]

        # near misses: one blocker away, same practice - lets the manager see "why not X?"
        near_ids = [eid for eid, b in excluded if len(b) == 1 and st.emp[eid]["role_family"] == role["family"]]
        near = sorted(self._score(role, near_ids, today), key=lambda r: -r["p"])[:5]
        blocker = dict(excluded)
        near_misses = [dict(self._person(r["employee_id"], role["start"]), success_probability=round(r["p"], 3),
                            blocker=blocker[r["employee_id"]][0]) for r in near]

        reasons = {}
        for _, b in excluded:
            key = reason_category(b[0])
            reasons[key] = reasons.get(key, 0) + 1
        return dict(role=self._role_view(role), candidates=candidates, near_misses=near_misses,
                    pool=dict(considered=len(eligible) + len(excluded), eligible=len(eligible),
                              excluded=len(excluded), exclusion_reasons=reasons),
                    fairness=self._fairness(eligible, [c["employee_id"] for c in candidates]),
                    model=dict(variant=self.meta["variant"], test_auc=self.meta["test_auc"]))

    def why_not(self, role, emp_id):
        blockers, warnings = filters.check(self.store, role, emp_id, today_ordinal())
        return dict(employee=self._person(emp_id, role["start"]), eligible=not blockers,
                    blockers=blockers, warnings=warnings)

    def eligibility(self, role, emp_id):
        out = self.why_not(role, emp_id)
        p, on_start, n = out.pop("employee"), *self.store.load_on(emp_id, role["start"])
        score = self._score(role, [emp_id], today_ordinal())[0]["p"] if out["eligible"] else None
        return dict(out, role=self._role_view(role), success_probability=score and round(score, 3),
                    workload=dict(today=p["workload_now"], on_start=on_start, after=on_start + role["alloc"],
                                  projects_on_start=n, current_projects=p["current_projects"]))

    # ------------------------------------------------------------------ scoring & explanation
    def _score(self, role, ids, today):
        if not ids:
            return []
        X = features.build(self.store, role, ids, know=today)
        raw = self.model.predict(X[self.feats])
        p = apply_calibrator(self.cal, raw)
        sv = self.explainer.shap_values(X[self.feats])
        sv = sv[1] if isinstance(sv, list) else sv
        bench_bonus = np.where(X.load_before.values == 0, 0.01, 0)        # POL09 tie-break: prefer bench
        rows = [dict(employee_id=eid, p=float(pi), x=X.iloc[i], shap=sv[i], raw=float(raw[i]))
                for i, (eid, pi) in enumerate(zip(X.employee_id, p))]
        order = np.argsort(-(p + bench_bonus))
        return [rows[i] for i in order]

    def _card(self, role, r, today, warnings, rank):
        st, x, eid = self.store, r["x"], r["employee_id"]
        scale = r["raw"] * (1 - r["raw"]) * 100                            # log-odds -> percentage points
        contrib = dict(zip(self.feats, r["shap"] * scale))
        factors = sorted(({"factor": g, "impact": round(sum(contrib.get(f, 0) for f in fs), 1)} for g, fs in GROUPS.items()),
                         key=lambda f: -abs(f["impact"]))

        held = {s: (p, acq, v, yrs) for s, p, acq, v, yrs in st.skills[eid]}
        used_before = set().union(*(a["skills_used"] for a in st.asg_by_emp[eid] if a["e"] < today)) if st.asg_by_emp[eid] else set()
        skills = [dict(skill=st.skill_name[s], required=mp, level=held[s][0] if s in held else None,
                       verified=bool(held.get(s, (0, 0, False))[2]), proven_on_project=s in used_before)
                  for s, mp in role["must"]]
        preferred = [dict(skill=st.skill_name[s], has=s in held) for s in role["nice"]]

        flags = list(warnings)
        e = st.emp[eid]
        exp = e["prior_exp"] + (today - e["join"]) / 365.25
        for s, (p, _, v, yrs) in held.items():
            relevant = s in dict(role["must"]) or s in role["nice"]
            if relevant and p and p >= 4 and not v and s not in used_before:
                flags.append(f"{st.skill_name[s]} claimed at {p}/5 but not verified or used on a project")
            if relevant and yrs > exp + 0.5:
                flags.append(f"{st.skill_name[s]}: {yrs:g} yrs of use exceeds {exp:.1f} yrs career")
        if e["total_experience_years"] is not None and float(e["total_experience_years"]) + 0.5 < exp - e["prior_exp"]:
            flags.append("Recorded total experience is lower than tenure - HR record inconsistent")
        if any(iss and exp_d and iss > exp_d for _, iss, exp_d in st.certs[eid]):
            flags.append("A certification has its issue date after its expiry date")
        if not e["email"]:
            flags.append("No email on record - assignment notification cannot be sent")
        for ls, le in st.leaves[eid]:
            if ls <= role["end"] and le >= role["start"]:
                flags.append(f"Planned leave {from_ordinal(ls)} to {from_ordinal(le)}")

        has_history = not np.isnan(x.past_rating)
        evidence = float(np.mean([x.verified_share, x.evidenced_share, 1 - x.must_unknown, float(has_history),
                                  1.0 if not any("claimed" in f or "inconsistent" in f for f in flags) else 0.4]))
        confidence = "High" if evidence >= 0.7 and has_history else ("Medium" if evidence >= 0.45 else "Low")

        similar = []
        if role.get("embedding") is not None:
            sims = st.proj_vecs @ role["embedding"]
            past = {a["project_id"] for a in st.asg_by_emp[eid] if a["e"] < today and a["project_id"] != role.get("project_id")}
            for pid in sorted((p for p in past if p in st.proj_index), key=lambda p: -sims[st.proj_index[p]])[:2]:
                pr = st.projects[pid]
                similar.append(dict(project=pr["project_name"], client_id=pr["client_id"], industry=pr["industry"],
                                    similarity=round(float(sims[st.proj_index[pid]]), 2)))

        return dict(rank=rank, **self._person(eid, role["start"]), success_probability=round(r["p"], 3),
                    confidence=confidence, evidence_score=round(evidence, 2), factors=factors,
                    skills=skills, preferred=preferred, experience_years=round(float(x.exp_years), 1),
                    domain_projects=int(x.domain_projects), similar_projects=similar,
                    past_rating=None if not has_history else round(float(x.past_rating), 2),
                    certifications=[st.cert_name[c] for c in role["mcerts"] + role["pcerts"]
                                    if any(cc == c and iss <= role["start"] and (ex is None or ex >= role["start"])
                                           for cc, iss, ex in st.certs[eid])],
                    workload_after=int(x.load_after), flags=flags,
                    explanation=self._explain_text(x, skills, similar, factors))

    def _person(self, eid, start):
        st, e = self.store, self.store.emp[eid]
        today = today_ordinal()
        live = [a for a in st.asg_by_emp[eid] if a["s"] <= today <= a["e"]]
        load_start, _ = st.load_on(eid, start)
        return dict(employee_id=eid, name=e["full_name"], email=e["email"], designation=e["designation"],
                    level=e["job_level"], practice=e["practice"], location=e["location"],
                    workload_now=sum(a["allocation_pct"] for a in live), workload_on_start=load_start,
                    current_projects=[dict(project=st.projects[a["project_id"]]["project_name"],
                                           allocation=a["allocation_pct"], ends=str(a["end_date"])) for a in live])

    @staticmethod
    def _explain_text(x, skills, similar, factors):
        met = sum(1 for s in skills if s["level"] and s["level"] >= s["required"])
        parts = [f"Meets {met}/{len(skills)} mandatory skills", f"{x.exp_years:.1f} yrs experience"]
        if similar:
            parts.append(f"most similar past project: {similar[0]['project']} ({similar[0]['similarity']:.0%} match)")
        if x.domain_projects:
            parts.append(f"{int(x.domain_projects)} project(s) in this industry")
        parts.append(f"{int(x.load_before)}% busy on start date -> {int(x.load_after)}% after")
        up = [f["factor"].lower() for f in factors if f["impact"] > 0.5][:2]
        down = [f["factor"].lower() for f in factors if f["impact"] < -0.5][:1]
        s = "; ".join(parts) + "."
        if up:
            s += f" Strongest factors: {' and '.join(up)}."
        if down:
            s += f" Held back by: {down[0]}."
        return s

    def _fairness(self, eligible, shortlist):
        """Four-fifths rule on the shortlist: women's share should be at least 80% of their share of the pool."""
        def share(ids):
            g = [self.gender.get(i) for i in ids]
            return round(sum(1 for x in g if x == "Female") / len(g), 3) if g else None
        pool, short = share(eligible), share(shortlist)
        ratio = (short / pool) if pool and short is not None else None
        if len(shortlist) < 5 or ratio is None:
            status = "too few candidates to assess"
        else:
            status = "ok" if ratio >= 0.8 else "review - women under-represented in shortlist"
        return dict(women_in_eligible_pool=pool, women_in_shortlist=short,
                    representation_ratio=round(ratio, 2) if ratio is not None else None, status=status,
                    note="Protected attributes are used only for this audit, never for ranking.")

    def _role_view(self, role):
        st = self.store
        p = st.projects.get(role.get("project_id"), {})
        filled = sum(1 for a in st.asg if a["project_role_id"] == role.get("role_id") and a["status"] in ("Upcoming", "Active"))
        return dict(role_id=role.get("role_id"), title=role["title"], project_id=role.get("project_id"),
                    project_name=p.get("project_name"), client_name=p.get("client_name"), industry=p.get("industry"),
                    priority=p.get("priority"), project_status=p.get("status"), description=p.get("description"),
                    filled=filled,
                    start=str(from_ordinal(role["start"])), end=str(from_ordinal(role["end"])),
                    allocation=role["alloc"], min_experience=role["min_exp"], headcount=role.get("headcount", 1),
                    mandatory_skills=[dict(skill=st.skill_name[s], min_level=m) for s, m in role["must"]],
                    preferred_skills=[st.skill_name[s] for s in role["nice"]],
                    mandatory_certs=[st.cert_name[c] for c in role["mcerts"]],
                    preferred_certs=[st.cert_name[c] for c in role["pcerts"]])
