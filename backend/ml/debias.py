"""Offline fairness job: correct historical ratings for gaps that qualifications do not explain.

Fits  rating ~ qualifications + group indicators  on the TRAINING period only, then removes the estimated
group effects from every rating. Protected attributes are read here (offline audit) and never in live scoring.
Run:  .venv\\Scripts\\python -m backend.ml.debias      (needs a training table from backend.ml.preprocess)
"""
import numpy as np
import pandas as pd

from ..config import ARTIFACTS
from ..db import conn, frame

QUALIFICATIONS = ["must_coverage", "must_gap", "nice_coverage", "exp_gap", "domain_projects", "sim_max", "overloaded"]
GROUPS = {"female": "Woman", "age_45_plus": "Age 45+ at assignment", "career_break": "Career break"}


def group_flags(df):
    df = df.copy()
    df["female"] = (df.gender == "Female").astype(float)
    age = (pd.to_datetime(df.start_date) - pd.to_datetime(df.date_of_birth)).dt.days / 365.25
    df["age_45_plus"] = (age >= 45).astype(float)
    df["career_break"] = (df.career_break_months > 0).astype(float)
    return df


def main():
    t = pd.read_parquet(ARTIFACTS / "training_table.parquet")
    people = frame("""SELECT s.employee_id, s.gender, s.date_of_birth, e.career_break_months
                      FROM restricted.employee_sensitive_attributes s JOIN employees e USING (employee_id)""")
    asg = frame("SELECT assignment_id, employee_id, start_date, performance_rating FROM assignments "
                "WHERE performance_rating IS NOT NULL")
    t = group_flags(t.merge(people, on="employee_id"))
    tr = t[t.split == "train"]

    groups = [g for g in GROUPS if tr[g].sum() >= 30]          # need enough cases to estimate an effect
    X = tr[QUALIFICATIONS].fillna(tr[QUALIFICATIONS].mean())
    X = np.column_stack([np.ones(len(tr)), X.values, tr[groups].values])
    y = tr.rating.values.astype(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    se = np.sqrt(np.diag(resid.var(ddof=X.shape[1]) * np.linalg.inv(X.T @ X)))
    k = 1 + len(QUALIFICATIONS)
    effects = {g: (beta[k + i], se[k + i]) for i, g in enumerate(groups)}

    a = group_flags(asg.merge(people, on="employee_id"))
    shift = sum(a[g] * effects[g][0] for g in groups)
    a["adjusted"] = (a.performance_rating - shift).clip(1, 5).round(2)
    with conn() as c:
        c.execute("TRUNCATE rating_adjustments")
        with c.cursor().copy("COPY rating_adjustments (assignment_id, raw_rating, adjusted_rating, method) FROM STDIN") as cp:
            for r in a.itertuples():
                cp.write_row([r.assignment_id, int(r.performance_rating), float(r.adjusted), "ols-unexplained-gap-v1"])

    lines = ["# Rating bias audit (training period 2018-2023)", "",
             "Rating gap per group after controlling for skills, experience, domain, similarity and overload:", "",
             "| Group | Unexplained rating gap | Std. error | 95% CI |", "|---|---|---|---|"]
    for g in GROUPS:
        if g in effects:
            b, s = effects[g]
            lines.append(f"| {GROUPS[g]} | {b:+.3f} | {s:.3f} | [{b - 1.96 * s:+.3f}, {b + 1.96 * s:+.3f}] |")
        else:
            lines.append(f"| {GROUPS[g]} | insufficient data ({int(tr[g].sum())} cases) - not corrected | | |")
    lines += ["", f"Adjusted {len(a):,} ratings; mean shift by gender: "
              + ", ".join(f"{k} {v:+.3f}" for k, v in (a.adjusted - a.performance_rating).groupby(a.gender).mean().items())]
    (ARTIFACTS / "bias_audit_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
