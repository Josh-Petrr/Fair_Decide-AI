"""Hard constraints from the policies table. Every exclusion gets a human-readable reason."""
from .store import from_ordinal


def check(store, role, emp_id, today):
    """Returns (blockers, warnings). Empty blockers = eligible."""
    e = store.emp[emp_id]
    pol = store.policy
    start = role["start"]
    blockers, warnings = [], []
    name = store.skill_name

    if e["employment_status"] == "Serving Notice":
        blockers.append(f"Serving notice - last working day {from_ordinal(e['exit'])}")
    elif e["employment_status"] == "On Long Leave":
        blockers.append("On long leave")
    if e["join"] > start - int(pol.get("NEW_JOINER_INDUCTION_DAYS", 14)):
        blockers.append(f"In induction (joined {from_ordinal(e['join'])})")
    window = int(pol.get("BLOCK_IF_LONG_LEAVE_WITHIN_DAYS", 30))
    for ls, le in store.leaves[emp_id]:
        if ls <= start + window and le >= start:
            blockers.append(f"On leave {from_ordinal(ls)} to {from_ordinal(le)}")

    held = {s: p for s, p, acq, _, _ in store.skills[emp_id] if acq is None or acq <= today}
    for s, mp in role["must"]:
        if s not in held:
            blockers.append(f"Missing {name[s]}")
        elif held[s] is None:
            blockers.append(f"{name[s]} level not recorded")
        elif held[s] < mp:
            blockers.append(f"{name[s]} {held[s]}/5 (needs {mp})")
    valid = {c for c, iss, exp in store.certs[emp_id] if iss and iss <= start and (exp is None or exp >= start)}
    for c in role["mcerts"]:
        if c not in valid:
            blockers.append(f"{store.cert_name[c]} not valid on start date")

    exp = e["prior_exp"] + max(0, today - e["join"]) / 365.25
    tol = float(pol.get("MIN_EXPERIENCE_TOLERANCE_YEARS", 1))
    if exp < role["min_exp"] - tol:
        blockers.append(f"{exp:.1f} yrs experience (needs {role['min_exp']:g})")
    elif exp < role["min_exp"]:
        warnings.append(f"Stretch: {exp:.1f} yrs vs {role['min_exp']:g} required")

    load, n = store.load_on(emp_id, start)
    cap = int(pol.get("MAX_ALLOCATION_PCT", 100))
    max_n = int(pol.get("PM_MAX_CONCURRENT_PROJECTS" if role["family"] == "pm" else "MAX_CONCURRENT_PROJECTS", 3))
    if load + role["alloc"] > cap:
        blockers.append(f"Would be at {load + role['alloc']}% on start date (already {load}%)")
    elif load + role["alloc"] > int(pol.get("WARN_ALLOCATION_PCT", 80)) and load > 0:
        warnings.append(f"High workload: {load + role['alloc']}% after assignment")
    if n >= max_n:
        blockers.append(f"Already on {n} projects")
    if any(a["project_id"] == role.get("project_id") and a["e"] >= today for a in store.asg_by_emp[emp_id]):
        blockers.append("Already on this project")
    return blockers, warnings
