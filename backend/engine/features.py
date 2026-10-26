"""Candidate x role features, computed point-in-time.

`know` = the date we evaluate a person's profile at (skills acquired, projects finished, ratings received).
Load is measured on the role's start date. For training, know = the past assignment's start date; for live
recommendations, know = today. The same code path is used for both, so the model sees identical features.
Protected attributes (gender, age, career break) are never read here.
"""
import numpy as np
import pandas as pd

FEATURES = [
    "must_coverage", "must_held", "must_gap", "must_surplus", "must_unknown", "nice_coverage",
    "exp_years", "exp_gap", "level", "same_family",
    "domain_projects", "total_projects", "past_rating", "sim_max", "sim_top3",
    "mcert_ok", "pcert_count", "verified_share", "evidenced_share",
    "load_before", "load_after", "concurrent", "overloaded", "alloc",
]


def build(store, role, emp_ids, know, exclude=None):
    """One row per employee. `exclude` = assignment id to ignore (the one being predicted, during training)."""
    sims_all = store.proj_vecs @ role["embedding"] if role.get("embedding") is not None else None
    must, nice = role["must"], set(role["nice"])
    rows = []
    for eid in emp_ids:
        e = store.emp[eid]
        held = {s: (p, v) for s, p, acq, v, _ in store.skills[eid] if acq is None or acq <= know}
        past = [a for a in store.asg_by_emp[eid] if a["e"] < know and a["assignment_id"] != exclude]

        # mandatory skills
        met = gap = surplus = unknown = 0
        held_must = [s for s, _ in must if s in held]
        for s, mp in must:
            if s not in held:
                gap += mp
                continue
            p = held[s][0]
            if p is None:
                unknown += 1
                gap += 1
            elif p >= mp:
                met += 1
                surplus += p - mp
            else:
                gap += mp - p
        n = max(len(must), 1)

        # evidence: matched skills verified by a manager / used on an earlier project
        used_before = set().union(*(a["skills_used"] for a in past)) if past else set()
        verified = sum(1 for s in held_must if held[s][1])
        evidenced = sum(1 for s in held_must if s in used_before)

        # experience and history
        exp = e["prior_exp"] + max(0, know - e["join"]) / 365.25
        ratings = [a["rating_adj"] for a in past if a["performance_rating"]]          # bias-corrected
        raw_ratings = [a["performance_rating"] for a in past if a["performance_rating"]]
        sims = []
        if sims_all is not None:
            sims = sorted((float(sims_all[store.proj_index[a["project_id"]]]) for a in past
                           if a["project_id"] != role.get("project_id") and a["project_id"] in store.proj_index),
                          reverse=True)

        # certifications valid on the role start date
        valid = {c for c, iss, exp_d in store.certs[eid] if iss and iss <= role["start"] and (exp_d is None or exp_d >= role["start"])}

        load, conc = store.load_on(eid, role["start"], exclude)
        rows.append(dict(
            employee_id=eid,
            must_coverage=met / n, must_held=len(held_must) / n, must_gap=gap / n,
            must_surplus=surplus / max(met, 1), must_unknown=unknown / n,
            nice_coverage=len(nice & held.keys()) / len(nice) if nice else np.nan,
            exp_years=exp, exp_gap=exp - role["min_exp"], level=e["level"],
            same_family=int(e["role_family"] == role["family"]),
            domain_projects=len({a["project_id"] for a in past if a["industry"] == role["industry"]}),
            total_projects=len({a["project_id"] for a in past}),
            past_rating=float(np.mean(ratings)) if ratings else np.nan,
            past_rating_raw=float(np.mean(raw_ratings)) if raw_ratings else np.nan,
            sim_max=sims[0] if sims else np.nan, sim_top3=float(np.mean(sims[:3])) if sims else np.nan,
            mcert_ok=int(all(c in valid for c in role["mcerts"])),
            pcert_count=sum(1 for c in role["pcerts"] if c in valid),
            verified_share=verified / len(held_must) if held_must else 0.0,
            evidenced_share=evidenced / len(held_must) if held_must else 0.0,
            load_before=load, load_after=load + role["alloc"], concurrent=conc,
            overloaded=int(load + role["alloc"] > 100), alloc=role["alloc"],
        ))
    return pd.DataFrame(rows, columns=["employee_id"] + FEATURES + ["past_rating_raw"])
