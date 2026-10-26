"""Train the suitability model (LightGBM), calibrate it, evaluate it, and save the artifacts.

Run:  .venv\\Scripts\\python -m backend.ml.train      (after backend.ml.preprocess)
"""
import json
import random

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import KFold

from ..config import ARTIFACTS, ROOT
from ..db import frame
from ..engine import features
from ..engine.store import Store

F = features.FEATURES
# +1: score may only rise with the feature, -1: only fall, 0: free
MONOTONE = {"must_coverage": 1, "must_held": 1, "must_gap": -1, "nice_coverage": 1, "domain_projects": 1,
            "past_rating": 1, "sim_max": 1, "sim_top3": 1, "mcert_ok": 1, "pcert_count": 1,
            "evidenced_share": 1, "overloaded": -1}
PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8,
              subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, seed=17,
              monotone_constraints_method="advanced")
# Historical ratings carry bias, so we compare: raw ratings / bias-corrected ratings / no ratings at all.
VARIANTS = {"Raw ratings": [c if c != "past_rating" else "past_rating_raw" for c in F],
            "Bias-corrected ratings": F,
            "Bias-corrected + reweighing": F,
            "No past ratings": [c for c in F if c != "past_rating"]}
WEIGHTED = {"Bias-corrected + reweighing"}
MONOTONE["past_rating_raw"] = 1
GROUP_OF = {}   # employee_id -> protected group label, filled offline in main()


def baseline_score(df):
    """Hand-weighted formula a manager might use - the benchmark the ML model must beat."""
    return (0.45 * df.must_coverage + 0.15 * df.nice_coverage.fillna(0.5)
            + 0.15 * (df.exp_gap / 5).clip(0, 1) + 0.10 * (df.domain_projects / 3).clip(0, 1)
            + 0.15 * ((df.past_rating.fillna(3) - 1) / 4))


def ece(y, p, bins=10):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return sum(abs(y[idx == b].mean() - p[idx == b].mean()) * (idx == b).mean() for b in range(bins) if (idx == b).any())


def ndcg(gains_in_pred_order, ideal_gains, k):
    disc = 1 / np.log2(np.arange(2, k + 2))
    dcg = (np.array(gains_in_pred_order[:k]) * disc[:len(gains_in_pred_order[:k])]).sum()
    idcg = (np.array(ideal_gains[:k]) * disc[:len(ideal_gains[:k])]).sum()
    return dcg / idcg if idcg else 0.0


def pick_calibrator(p, y):
    """Choose none / sigmoid / isotonic by 5-fold cross-validated ECE on the validation year, then fit on all of it."""
    lg = lambda q: np.log(np.clip(q, 1e-6, 1 - 1e-6) / (1 - np.clip(q, 1e-6, 1 - 1e-6))).reshape(-1, 1)
    makers = {"sigmoid": lambda pp, yy: LogisticRegression().fit(lg(pp), yy),
              "isotonic": lambda pp, yy: IsotonicRegression(out_of_bounds="clip").fit(pp, yy)}
    cv = {"none": [], "sigmoid": [], "isotonic": []}
    for a, b in KFold(5, shuffle=True, random_state=17).split(p):
        cv["none"].append(ece(y[b], p[b]))
        for k, make in makers.items():
            cv[k].append(ece(y[b], apply_calibrator({"kind": k, "model": make(p[a], y[a])}, p[b])))
    kind = min(cv, key=lambda k: np.mean(cv[k]))
    return {"kind": kind, "model": makers[kind](p, y) if kind != "none" else None}, {k: np.mean(v) for k, v in cv.items()}


def apply_calibrator(cal, p):
    if cal["kind"] == "sigmoid":
        q = np.clip(p, 1e-6, 1 - 1e-6)
        return cal["model"].predict_proba(np.log(q / (1 - q)).reshape(-1, 1))[:, 1]
    if cal["kind"] == "isotonic":
        return cal["model"].predict(p)
    return p


def reweigh(df):
    """Kamiran & Calders reweighing: weight = P(group) * P(label) / P(group, label), so that labels become
    independent of protected group in training. Group is read offline from the restricted schema only."""
    g = df.employee_id.map(GROUP_OF).fillna("unknown")
    pg, py = g.value_counts(normalize=True), df.success.value_counts(normalize=True)
    pgy = pd.crosstab(g, df.success, normalize=True)
    return np.array([pg[a] * py[b] / pgy.loc[a, b] for a, b in zip(g, df.success)])


def fit_variant(feats, tr, va, weighted=False):
    params = dict(PARAMS, monotone_constraints=[MONOTONE.get(c, 0) for c in feats])
    model = lgb.train(params, lgb.Dataset(tr[feats], tr.success, weight=reweigh(tr) if weighted else None),
                      num_boost_round=2000, valid_sets=[lgb.Dataset(va[feats], va.success)],
                      callbacks=[lgb.early_stopping(100, verbose=False)])
    cal, cv = pick_calibrator(model.predict(va[feats]), va.success.values)
    return model, cal, cv


def ranking_eval(store, variants, test_rows, ability, sens):
    """Rebuild each test role's candidate pool and compare rankings with the true (bias-free) suitability."""
    out, picks = [], []
    rng = random.Random(17)
    for role_id, g in test_rows.groupby("role_id"):
        role = store.role_spec(role_id)
        role["start"] = min(g.start_ord)
        pool = [eid for eid, e in store.emp.items()
                if e["role_family"] == role["family"] and e["join"] <= role["start"] - 14
                and (e["exit"] is None or e["exit"] > role["start"])]
        X = features.build(store, role, pool, know=role["start"])
        X = X[(X.load_after <= 100) & (X.exp_gap >= -1)].reset_index(drop=True)
        if len(X) < 10:
            continue
        truth = (1.2 * X.must_coverage + 0.4 * X.nice_coverage.fillna(0) + 0.5 * (X.exp_gap / 3).clip(-1, 1)
                 + 0.5 * (X.domain_projects / 3).clip(0, 1) + 0.25 * (X.pcert_count > 0)
                 + 0.5 * X.employee_id.map(ability).fillna(0))
        gains = truth.rank(pct=True).values ** 3                     # graded relevance, top candidates dominate
        ideal = np.sort(gains)[::-1]
        true_rank = truth.rank(ascending=False).values
        scores = {name: apply_calibrator(cal, m.predict(X[feats])) for name, (m, cal, feats) in variants.items()}
        scores["Baseline formula"] = baseline_score(X).values
        scores["Random"] = np.array([rng.random() for _ in range(len(X))])
        for name, s in scores.items():
            order = np.argsort(-s)
            out.append(dict(method=name, ndcg10=ndcg(gains[order], ideal, 10),
                            p5=(true_rank[order[:5]] <= 5).mean(), pool=len(X)))
            if name in variants:
                sel = np.zeros(len(X), bool)
                sel[order[:5]] = True
                picks += [dict(method=name, employee_id=e, selected=s_, merit_top5=t <= 5)
                          for e, s_, t in zip(X.employee_id, sel, true_rank)]
    res = pd.DataFrame(out).groupby("method")[["ndcg10", "p5", "pool"]].mean()
    p = pd.DataFrame(picks).merge(sens, on="employee_id")
    fair = p.groupby(["method", "gender"]).agg(selection_rate=("selected", "mean"))
    fair["selected_when_truly_top5"] = p[p.merit_top5].groupby(["method", "gender"]).selected.mean()
    return res, fair, len(set(test_rows.role_id))


def main():
    df = pd.read_parquet(ARTIFACTS / "training_table.parquet")
    tr, va, te = (df[df.split == s] for s in ("train", "valid", "test"))
    y = te.success.values
    groups = frame("""SELECT s.employee_id, s.gender, e.career_break_months > 0 AS brk
                      FROM restricted.employee_sensitive_attributes s JOIN employees e USING (employee_id)""")
    GROUP_OF.update({r.employee_id: f"{r.gender}|{'break' if r.brk else 'no-break'}" for r in groups.itertuples()})
    variants, clf, cv_rows = {}, [], {}
    for name, feats in VARIANTS.items():
        model, cal, cv = fit_variant(feats, tr, va, weighted=name in WEIGHTED)
        variants[name] = (model, cal, feats)
        raw = model.predict(te[feats])
        p = apply_calibrator(cal, raw)
        clf.append(dict(model=name, AUC=roc_auc_score(y, p), Brier=brier_score_loss(y, p),
                        ECE_raw=ece(y, raw), ECE_final=ece(y, p), calibration=cal["kind"], trees=model.best_iteration))
        cv_rows[name] = cv
    clf.append(dict(model="Baseline formula", AUC=roc_auc_score(y, baseline_score(te))))
    clf = pd.DataFrame(clf).set_index("model")

    store = Store()
    gt = pd.read_csv(ROOT / "data" / "_ground_truth" / "assignment_latent_scores.csv")
    asg = pd.read_csv(ROOT / "data" / "assignments.csv")
    ability = gt.merge(asg[["assignment_id", "employee_id"]], on="assignment_id").groupby("employee_id").employee_ability.first()
    sens = pd.read_csv(ROOT / "data" / "employee_sensitive_attributes.csv")[["employee_id", "gender"]]
    te_roles = te.merge(asg[["assignment_id", "project_role_id"]], on="assignment_id").rename(columns={"project_role_id": "role_id"})
    te_roles["start_ord"] = pd.to_datetime(te_roles.start_date).map(lambda d: d.toordinal())
    rank, fair, n_roles = ranking_eval(store, variants, te_roles, ability, sens)

    # production choice: the variant with the smallest equal-opportunity gap, unless it ranks clearly worse
    gaps = {m: abs(fair.loc[(m, "Female"), "selected_when_truly_top5"] - fair.loc[(m, "Male"), "selected_when_truly_top5"])
            for m in variants}
    best_ndcg = rank.loc[list(variants), "ndcg10"].max()
    chosen = min((m for m in variants if rank.loc[m, "ndcg10"] >= best_ndcg - 0.01), key=gaps.get)
    model, cal, feats = variants[chosen]
    model.save_model(str(ARTIFACTS / "suitability_lgbm.txt"))
    joblib.dump(cal, ARTIFACTS / "calibrator.joblib")
    meta = dict(variant=chosen, features=feats, calibration=cal["kind"], trees=model.best_iteration,
                test_auc=round(float(clf.loc[chosen, "AUC"]), 4), base_rate=round(float(tr.success.mean()), 4),
                equal_opportunity_gap=round(float(gaps[chosen]), 4))
    (ARTIFACTS / "model_meta.json").write_text(json.dumps(meta, indent=2))
    imp = pd.Series(model.feature_importance("gain"), index=feats).sort_values(ascending=False)

    lines = ["# Model evaluation report", "",
             f"Train {len(tr):,} rows (2018-2023) | Validation {len(va):,} (2024) | Test {len(te):,} (2025-26)", "",
             "## 1. Success prediction on the test period (labels = historical ratings, which contain bias)", "",
             clf.round(3).to_markdown(), "",
             "Calibration chosen by 5-fold CV ECE on 2024: " + "; ".join(
                 f"{m}: " + ", ".join(f"{k}={v:.3f}" for k, v in c.items()) for m, c in cv_rows.items()), "",
             f"## 2. Ranking quality on {n_roles} test roles vs. true (bias-free) suitability", "",
             rank.round(3).rename(columns={"ndcg10": "NDCG@10", "p5": "Precision@5 (true top-5)",
                                           "pool": "Avg pool"}).to_markdown(), "",
             "## 3. Fairness of the top-5 shortlist by gender", "",
             fair.round(3).to_markdown(), "",
             f"Equal-opportunity gap: " + ", ".join(f"{m} = {g:.3f}" for m, g in gaps.items()), "",
             f"**Production model: {chosen}**", "",
             "## 4. Feature importance (gain) of the production model", "",
             (imp / imp.sum()).round(3).to_frame("share").to_markdown()]
    (ARTIFACTS / "evaluation_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
