"""Real-world fairness stress tests for the recommender. READ-ONLY: nothing is written to the database.

Two kinds of test:
  * Counterfactual twins - copy a real candidate in memory, change ONE thing (gender, name, career break,
    maternity/paternity leave, age, self-rated skills, ...) and re-score them on the same real open role.
  * Group outcomes - run every open demand through filters + model and compare outcomes between groups,
    and replay the 2025-26 test period against the hidden bias-free "true suitability" from the generator.

Run:  .venv\\Scripts\\python -m tests.fairness_audit
Writes backend/ml/artifacts/fairness_audit.json (all numbers used in reports/fairness_and_validation_report.md).
"""
import json
import random
import time
from collections import defaultdict

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from backend.config import ARTIFACTS, ROOT
from backend.db import frame
from backend.engine import features, filters
from backend.engine.recommender import Recommender
from backend.engine.store import PROTECTED, from_ordinal, today_ordinal
from backend.ml import train
from backend.ml.train import apply_calibrator

T0 = time.time()
R = {}                      # every result that goes into the report
rng = random.Random(17)
rec = Recommender()
st, today = rec.store, today_ordinal()
R["as_of"] = str(from_ordinal(today))


def log(*a):
    print(f"[{time.time() - T0:5.0f}s]", *a, flush=True)


# ------------------------------------------------------------------------------------------- people & groups
sens = frame("""SELECT s.employee_id, s.gender, s.date_of_birth, e.career_break_months, e.location, e.work_mode
                FROM restricted.employee_sensitive_attributes s JOIN employees e USING (employee_id)""").set_index("employee_id")
sens = sens.reindex(list(st.emp))
sens["gender"] = sens.gender.fillna("Not recorded")
sens["career_break_months"] = sens.career_break_months.fillna(0)
sens["age"] = (pd.Timestamp(from_ordinal(today)) - pd.to_datetime(sens.date_of_birth)).dt.days / 365.25
sens["age_band"] = pd.cut(sens.age, [0, 30, 40, 50, 99], right=False, labels=["<30", "30-39", "40-49", "50+"]).astype(str)
sens["career_break"] = np.where(sens.career_break_months > 0, "Career break", "No break")
sens["gender_break"] = sens.gender + " / " + sens.career_break
active = [e for e, x in st.emp.items() if x["employment_status"] != "Exited"]
R["population"] = {
    "active_people": len(active),
    "breaks": sens.loc[sens.index.isin(active)].groupby("gender").agg(
        people=("career_break_months", "size"), with_break=("career_break_months", lambda s: int((s > 0).sum())),
        avg_break_months=("career_break_months", lambda s: round(float(s[s > 0].mean()), 1))).to_dict("index")}


def score(role, ids):
    X = features.build(st, role, ids, know=today)
    return dict(zip(X.employee_id, apply_calibrator(rec.cal, rec.model.predict(X[rec.feats])))), X


# ------------------------------------------------------------------------------------------- 0. design checks
emp_keys = set(next(iter(st.emp.values())).keys())
R["design"] = {
    "protected_columns": list(PROTECTED),
    "protected_in_model_features": sorted(set(rec.feats) & set(PROTECTED)),
    "protected_loaded_into_engine": sorted(emp_keys & {"gender", "date_of_birth", "age_band", "career_break_months", "first_name"}),
    "location_or_work_mode_in_features": sorted(set(rec.feats) & {"location", "work_mode", "full_name"}),
}
log("design", R["design"])

# ------------------------------------------------------------------------------------------- 1. live open demands
open_roles = [rid for rid, r in st.roles.items() if r["demand_status"] == "Open"]
elig, excl, short = {}, defaultdict(list), {}
for rid in open_roles:
    role = st.role_spec(rid)
    ok = []
    for eid in active:
        b, _ = filters.check(st, role, eid, today)
        (excl[rid].append((eid, b)) if b else ok.append(eid))
    elig[rid] = ok
    if ok:
        p, _ = score(role, ok)
        short[rid] = sorted(ok, key=lambda e: -p[e])[:10]
log("open roles", len(open_roles), "with candidates", len(short))


def group_table(col):
    """Eligibility pass rate (filters) and shortlist rate (model, top-10) per group, pooled over all open roles."""
    rows = defaultdict(lambda: dict(considered=0, eligible=0, shortlisted=0))
    for rid in short:
        considered = elig[rid] + [e for e, _ in excl[rid]]
        for e in considered:
            rows[sens.at[e, col]]["considered"] += 1
        for e in elig[rid]:
            rows[sens.at[e, col]]["eligible"] += 1
        for e in short[rid]:
            rows[sens.at[e, col]]["shortlisted"] += 1
    t = pd.DataFrame(rows).T
    t["pass_rate"] = t.eligible / t.considered
    t["shortlist_rate"] = t.shortlisted / t.eligible
    t["filter_ratio"] = t.pass_rate / t.pass_rate.max()
    t["shortlist_ratio"] = t.shortlist_rate / t.shortlist_rate.max()
    return t.round(4).to_dict("index")


R["live_groups"] = {c: group_table(c) for c in ("gender", "career_break", "gender_break", "age_band", "location", "work_mode")}

monitor = [rec._fairness(elig[r], short[r])["status"] for r in short]
R["live_monitor"] = pd.Series(monitor).value_counts().to_dict()
R["monitor_unit"] = {
    "all_men_shortlist": rec._fairness([e for e in active if sens.at[e, "gender"] == "Female"][:20]
                                       + [e for e in active if sens.at[e, "gender"] == "Male"][:20],
                                       [e for e in active if sens.at[e, "gender"] == "Male"][:10])["status"],
    "balanced_shortlist": rec._fairness([e for e in active if sens.at[e, "gender"] == "Female"][:20]
                                        + [e for e in active if sens.at[e, "gender"] == "Male"][:20],
                                        [e for e in active if sens.at[e, "gender"] == "Female"][:5]
                                        + [e for e in active if sens.at[e, "gender"] == "Male"][:5])["status"]}

# why people are filtered out, per gender (leave vs everything else)
reason = defaultdict(lambda: defaultdict(int))
for rid in short:
    for e, b in excl[rid]:
        g = sens.at[e, "gender"]
        for x in b:
            if x.startswith("On leave"):
                reason[g]["leave in first 30 days"] += 1
            elif x == "On long leave":
                reason[g]["status: on long leave"] += 1
            elif "yrs experience" in x:
                reason[g]["not enough experience"] += 1
per_g = {g: sum(1 for r in short for e in elig[r] + [x for x, _ in excl[r]] if sens.at[e, "gender"] == g) for g in ("Female", "Male")}
R["exclusion_reasons_per_1000_checks"] = {g: {k: round(1000 * v / per_g[g], 2) for k, v in reason[g].items()} for g in reason}
lv = frame("""SELECT l.employee_id, l.leave_type, s.gender FROM employee_leaves l
              JOIN restricted.employee_sensitive_attributes s USING (employee_id)
              WHERE l.status = 'Approved' AND l.end_date - l.start_date > 10 AND l.end_date >= fd_as_of()""")
R["blocking_leaves_by_type"] = lv.groupby(["leave_type", "gender"]).size().unstack(fill_value=0).to_dict("index")
log("live groups done")

# ------------------------------------------------------------------------------------------- 2. twins
contenders = [(rid, e) for rid in short for e in short[rid][:5]]          # real top-5 people on real roles
rng.shuffle(contenders)
contenders = contenders[:400]
outside = [(rid, e) for rid in short for e in short[rid][5:10]]           # ranked 6-10: could they climb into the top 5?
rng.shuffle(outside)
outside = outside[:400]
TWINS = []
BASE = {}


def base_scores(rid, role):
    if rid not in BASE:
        BASE[rid] = score(role, elig[rid])[0]
    return BASE[rid]


def twin(eid, **changes):
    tid = f"{eid}~{len(TWINS)}"
    st.emp[tid] = {**st.emp[eid], **changes, "employee_id": tid}
    st.skills[tid] = list(st.skills[eid])
    st.certs[tid] = list(st.certs[eid])
    st.leaves[tid] = list(st.leaves[eid])
    st.asg_by_emp[tid] = [dict(a) for a in st.asg_by_emp[eid]]
    rec.gender[tid] = rec.gender.get(eid)
    TWINS.append(tid)
    return tid


def add_leave(tid, start, days):
    if days - 1 > 10:                                     # same rule as Store: only approved leave > 10 days counts
        st.leaves[tid].append((start, start + days - 1))


def run_twins(make, label, people=None):
    """make(role, eid) -> twin id. Returns score change (percentage points) and top-5 flips."""
    people = people or contenders
    d, flips, blocked, by_g = [], 0, 0, defaultdict(list)
    for rid, eid in people:
        role = st.role_spec(rid)
        tid = make(role, eid)
        b, _ = filters.check(st, role, tid, today)
        if b:
            blocked += 1
            continue
        p, _ = score(role, [eid, tid])
        delta = 100 * (p[tid] - p[eid])
        d.append(delta)
        by_g[sens.at[eid, "gender"]].append(delta)
        q = {k: v for k, v in base_scores(rid, role).items() if k != eid}
        rank_before = 1 + sum(v > p[eid] for v in q.values())
        rank_after = 1 + sum(v > p[tid] for v in q.values())
        flips += (rank_before <= 5) != (rank_after <= 5)
    d = np.array(d) if d else np.zeros(1)
    out = dict(cases=len(people), blocked_by_filters=blocked, mean_change_pp=round(float(d.mean()), 2),
               min_change_pp=round(float(d.min()), 2), max_change_pp=round(float(d.max()), 2),
               max_abs_change_pp=round(float(np.abs(d).max()), 4), left_or_joined_top5=flips,
               by_gender={g: round(float(np.mean(v)), 2) for g, v in by_g.items()})
    log(label, out)
    return out


OPP = {"Female": ("Rahul", "Verma"), "Male": ("Priya", "Iyer")}
T = R["twins"] = {}
def swap_gender(r, e):
    t = twin(e, full_name=" ".join(OPP.get(sens.at[e, "gender"], OPP["Male"])))
    rec.gender[t] = "Male" if rec.gender.get(e) == "Female" else "Female"
    return t


T["gender_and_name_swap"] = run_twins(swap_gender, "gender + name swap")
T["location_and_work_mode_change"] = run_twins(lambda r, e: twin(e, location="Guwahati" if st.emp[e]["location"] != "Guwahati" else "Pune"),
                                             "location change")
for months in (6, 12, 18, 24):
    T[f"career_break_{months}m_experience_lost"] = run_twins(
        lambda r, e, m=months: twin(e, prior_exp=max(0.0, st.emp[e]["prior_exp"] - m / 12)), f"break {months}m")


def returner(r, e, months=12):
    """Took a long leave/break during tenure: tenure still counts, but no project was done in that window."""
    t = twin(e)
    lo, hi = today - 365 - months * 30, today - 365
    st.asg_by_emp[t] = [a for a in st.asg_by_emp[t] if not (a["s"] <= hi and a["e"] >= lo)]
    return t


T["returner_missed_12m_of_projects"] = run_twins(returner, "returner 12m")
T["past_maternity_leave_6m_ended"] = run_twins(lambda r, e: (lambda t: (add_leave(t, today - 400, 182), t)[1])(twin(e)), "past maternity")
T["past_paternity_leave_15d_ended"] = run_twins(lambda r, e: (lambda t: (add_leave(t, today - 200, 15), t)[1])(twin(e)), "past paternity")


def upcoming(days, offset):
    return lambda r, e: (lambda t: (add_leave(t, r["start"] + offset, days), t)[1])(twin(e))


for name, days, offset in [("maternity_182d_starts_1w_after_role", 182, 7), ("paternity_15d_starts_1w_after_role", 15, 7),
                           ("paternity_10d_starts_1w_after_role", 10, 7), ("maternity_182d_starts_5w_after_role", 182, 35),
                           ("paternity_15d_starts_5w_after_role", 15, 35), ("earned_leave_12d_starts_1w_after_role", 12, 7)]:
    T[name] = run_twins(upcoming(days, offset), name)

# same leave, different gender => same outcome?
same = []
for rid, eid in contenders[:150]:
    role = st.role_spec(rid)
    a, b = twin(eid), twin(eid)
    rec.gender[a], rec.gender[b] = "Female", "Male"
    add_leave(a, role["start"] + 7, 15)
    add_leave(b, role["start"] + 7, 15)
    same.append(filters.check(st, role, a, today) == filters.check(st, role, b, today))
T["identical_leave_identical_outcome_any_gender"] = f"{sum(same)}/{len(same)}"

# planned-leave flag visible to the manager when leave starts after the 30-day window
flagged = 0
for rid, eid in contenders[:100]:
    role = st.role_spec(rid)
    t = twin(eid)
    add_leave(t, role["start"] + 35, 182)
    p, X = score(role, [t])
    r = dict(employee_id=t, p=p[t], x=X.iloc[0], shap=np.zeros(len(rec.feats)), raw=0.5)
    flagged += any("Planned leave" in f for f in rec._card(role, r, today, [], 1)["flags"])
T["late_maternity_flag_shown"] = f"{flagged}/100"


def inflate(r, e, step=1):
    t = twin(e)
    must = dict(r["must"])
    st.skills[t] = [(s, min(5, p + step) if (p and s in must) else p, acq, False if s in must else v, y)
                    for s, p, acq, v, y in st.skills[e]]
    return t


T["self_rating_plus1_unverified"] = run_twins(inflate, "self-rating +1 unverified")
T["self_rating_plus1_unverified_ranked_6_10"] = run_twins(inflate, "self-rating +1 (ranked 6-10)", outside)
T["verified_by_manager"] = run_twins(lambda r, e: (lambda t: (st.skills.__setitem__(
    t, [(s, p, a, True, y) for s, p, a, v, y in st.skills[e]]), t)[1])(twin(e)), "manager verified")
T["older_plus10y_experience"] = run_twins(lambda r, e: twin(e, prior_exp=st.emp[e]["prior_exp"] + 10), "+10y")

T["older_plus20y_experience"] = run_twins(lambda r, e: twin(e, prior_exp=st.emp[e]["prior_exp"] + 20), "+20y")


def no_ratings(r, e):
    t = twin(e)
    for a in st.asg_by_emp[t]:
        a["performance_rating"] = None
    return t


T["no_past_ratings"] = run_twins(no_ratings, "no ratings")
T["verified_by_manager_ranked_6_10"] = run_twins(lambda r, e: (lambda t: (st.skills.__setitem__(
    t, [(s, p, a, True, y) for s, p, a, v, y in st.skills[e]]), t)[1])(twin(e)), "manager verified (6-10)", outside)

# real people with a break: what if the break had never happened?
real_break = [(rid, e) for rid in short for e in elig[rid] if sens.at[e, "career_break_months"] > 0]
rng.shuffle(real_break)
rb = defaultdict(list)
for rid, e in real_break[:600]:
    role = st.role_spec(rid)
    t = twin(e, prior_exp=st.emp[e]["prior_exp"] + sens.at[e, "career_break_months"] / 12)
    p, _ = score(role, [e, t])
    rb[sens.at[e, "gender"]].append(100 * (p[e] - p[t]))
blocked_by_break = defaultdict(int)
for rid in short:
    role = st.role_spec(rid)
    for e, b in excl[rid]:
        if len(b) == 1 and "yrs experience" in b[0] and sens.at[e, "career_break_months"] > 0:
            t = twin(e, prior_exp=st.emp[e]["prior_exp"] + sens.at[e, "career_break_months"] / 12)
            blocked_by_break[sens.at[e, "gender"]] += not filters.check(st, role, t, today)[0]
R["real_break_penalty"] = {g: dict(cases=len(v), mean_pp=round(float(np.mean(v)), 2), worst_pp=round(float(np.min(v)), 2))
                           for g, v in rb.items()}
R["blocked_only_because_of_break"] = dict(blocked_by_break)
log("real break", R["real_break_penalty"], R["blocked_only_because_of_break"])

for t in TWINS:                                            # leave the engine exactly as it was
    for d in (st.emp, st.skills, st.certs, st.leaves, st.asg_by_emp, rec.gender):
        d.pop(t, None)

# ------------------------------------------------------------------------------------------- 3. raw vs corrected ratings
rows = []
for rid in short:
    role = st.role_spec(rid)
    X = features.build(st, role, elig[rid], know=today)
    pc = apply_calibrator(rec.cal, rec.model.predict(X[rec.feats]))
    Xr = X.copy()
    Xr["past_rating"] = Xr.past_rating_raw
    pr = apply_calibrator(rec.cal, rec.model.predict(Xr[rec.feats]))
    top_c, top_r = set(X.employee_id[np.argsort(-pc)[:10]]), set(X.employee_id[np.argsort(-pr)[:10]])
    for e, a, b in zip(X.employee_id, pc, pr):
        rows.append(dict(group=sens.at[e, "gender_break"], change=100 * (a - b), in_c=e in top_c, in_r=e in top_r))
d = pd.DataFrame(rows)
R["rating_correction"] = d.groupby("group").agg(cases=("change", "size"), mean_change_pp=("change", "mean"),
                                                 shortlisted_raw=("in_r", "sum"), shortlisted_corrected=("in_c", "sum")).round(2).to_dict("index")
log("rating correction", R["rating_correction"])

# ------------------------------------------------------------------------------------------- 4. proxy leakage
tt = pd.read_parquet(ARTIFACTS / "training_table.parquet").merge(sens[["gender", "career_break_months", "age"]], left_on="employee_id", right_index=True)
leak = {}
for name, y in [("gender (Female)", (tt.gender == "Female").astype(int)), ("career break", (tt.career_break_months > 0).astype(int)),
                ("age 40+", (tt.age >= 40).astype(int))]:
    pred = np.zeros(len(tt))
    for a, b in GroupKFold(5).split(tt, y, groups=tt.employee_id):      # a person is never in both train and test
        m = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=15, verbose=-1)
        m.fit(tt.iloc[a][rec.feats], y.iloc[a])
        pred[b] = m.predict_proba(tt.iloc[b][rec.feats])[:, 1]
    leak[name] = round(float(roc_auc_score(y, pred)), 3)
R["proxy_leakage_auc"] = leak
log("leakage", leak)

# ------------------------------------------------------------------------------------------- 5. bias-free truth, by group
asg = pd.read_csv(ROOT / "data" / "assignments.csv")
gt = pd.read_csv(ROOT / "data" / "_ground_truth" / "assignment_latent_scores.csv")
ability = gt.merge(asg[["assignment_id", "employee_id"]], on="assignment_id").groupby("employee_id").employee_ability.first()
te = tt[tt.split == "test"].merge(asg[["assignment_id", "project_role_id"]], on="assignment_id").rename(columns={"project_role_id": "role_id"})
te["start_ord"] = pd.to_datetime(te.start_date).map(lambda x: x.toordinal())
variants = {"Production": (rec.model, rec.cal, rec.feats)}
truth = {}
for col in ("gender", "career_break", "gender_break", "age_band"):
    s = sens.reset_index()[["employee_id", col]].rename(columns={col: "gender"})
    _, fair, n = train.ranking_eval(st, variants, te, ability, s)
    truth[col] = fair.loc["Production"].round(3).to_dict("index")
    log("truth", col, truth[col])
R["truth_by_group"] = truth
R["truth_roles"] = int(n)

# age: was the injected age bias ever measurable in the training years?
a2 = asg.merge(sens[["date_of_birth"]], left_on="employee_id", right_index=True)
a2["age"] = (pd.to_datetime(a2.start_date) - pd.to_datetime(a2.date_of_birth)).dt.days / 365.25
a2["year"] = pd.to_datetime(a2.start_date).dt.year
R["assignments_age45_by_period"] = {"2018-2023 (training)": int(((a2.age >= 45) & (a2.year <= 2023)).sum()),
                                    "2024-2026": int(((a2.age >= 45) & (a2.year >= 2024)).sum()),
                                    "oldest_age_at_assignment": round(float(a2.age.max()), 1)}
R["seconds"] = round(time.time() - T0)
(ARTIFACTS / "fairness_audit.json").write_text(json.dumps(R, indent=2, default=str))
log("saved", ARTIFACTS / "fairness_audit.json")
