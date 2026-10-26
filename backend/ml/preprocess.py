"""Build the point-in-time training table from completed, rated assignments.

Run:  .venv\\Scripts\\python -m backend.ml.preprocess
Output: backend/ml/artifacts/training_table.parquet + preprocessing_report.md
"""
from datetime import date

import pandas as pd

from ..config import ARTIFACTS
from ..engine import features
from ..engine.store import PROTECTED, Store

SPLITS = [("train", date(2024, 1, 1)), ("valid", date(2025, 1, 1)), ("test", date(9999, 1, 1))]


def split_of(start):
    return next(name for name, before in SPLITS if start < before)


def main():
    store = Store()
    rows = []
    for a in store.asg:
        if a["status"] != "Completed" or not a["performance_rating"] or not a["project_role_id"]:
            continue
        role = store.role_spec(a["project_role_id"])
        role.update(start=a["s"], alloc=a["allocation_pct"])          # this person's actual stint
        f = features.build(store, role, [a["employee_id"]], know=a["s"], exclude=a["assignment_id"]).iloc[0].to_dict()
        f.update(assignment_id=a["assignment_id"], project_id=a["project_id"], role_family=role["family"],
                 start_date=a["start_date"], rating=a["performance_rating"],
                 success=int(a["performance_rating"] >= 4), split=split_of(a["start_date"]))
        rows.append(f)
    df = pd.DataFrame(rows)
    assert not set(PROTECTED) & set(df.columns), "protected attribute leaked into training table"
    df.to_parquet(ARTIFACTS / "training_table.parquet", index=False)

    # ---- report
    lines = ["# Preprocessing report", "", f"Rows: {len(df):,} completed & rated assignments", "",
             "| Split | Rows | Period | Success rate (rating >= 4) |", "|---|---|---|---|"]
    for name, g in df.groupby("split", sort=False):
        lines.append(f"| {name} | {len(g):,} | {g.start_date.min()} .. {g.start_date.max()} | {g.success.mean():.1%} |")
    lines += ["", "| Feature | Missing | Mean | Corr. with success |", "|---|---|---|---|"]
    for c in features.FEATURES:
        lines.append(f"| {c} | {df[c].isna().mean():.1%} | {df[c].mean():.2f} | {df[c].corr(df.success):+.2f} |")
    lines += ["", f"Protected attributes excluded: {', '.join(PROTECTED)}"]
    (ARTIFACTS / "preprocessing_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
