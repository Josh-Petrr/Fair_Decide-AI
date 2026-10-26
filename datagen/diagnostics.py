"""Sanity checks on the generated data: headcount over time, fill rates, utilisation, distributions."""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
TODAY = pd.Timestamp("2026-10-26")


def main():
    emp = pd.read_csv(DATA / "employees.csv", parse_dates=["date_of_joining", "exit_date"])
    asg = pd.read_csv(DATA / "assignments.csv", parse_dates=["start_date", "end_date"])
    roles = pd.read_csv(DATA / "project_roles.csv")
    prj = pd.read_csv(DATA / "projects.csv", parse_dates=["start_date", "end_date"])
    ec = pd.read_csv(DATA / "employee_certifications.csv", parse_dates=["expiry_date"])

    print("Headcount vs allocated FTE on 1 July of each year")
    for y in range(2019, 2027):
        d = pd.Timestamp(f"{y}-07-01")
        hc = ((emp.date_of_joining <= d) & (emp.exit_date.isna() | (emp.exit_date >= d))).sum()
        live = asg[(asg.start_date <= d) & (asg.end_date >= d)]
        fte = live.allocation_pct.sum() / 100
        print(f"  {y}: headcount {hc:4d}  allocated FTE {fte:6.1f}  utilisation {fte / hc:5.1%}  "
              f"active projects {((prj.start_date <= d) & (prj.end_date >= d)).sum()}")
    print("\nDemand status:", roles.demand_status.value_counts().to_dict())
    print("Assignment status:", asg.status.value_counts().to_dict())
    print("Ratings:", asg.performance_rating.value_counts(normalize=True).sort_index().round(3).to_dict())
    cur = emp[emp.employment_status != "Exited"]
    print("Levels (current):", cur.job_level.value_counts().sort_index().to_dict())
    print("Locations:", cur.location.value_counts().to_dict())
    print("Certs per current employee:", round(ec[ec.employee_id.isin(cur.employee_id)].shape[0] / len(cur), 2),
          "| expired share:", round((ec.expiry_date < TODAY).mean(), 3))
    print("Assignments per employee (ever staffed):", round(asg.groupby("employee_id").size().mean(), 1))


if __name__ == "__main__":
    main()
