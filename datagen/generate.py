"""Generate realistic synthetic workforce data for FairDecide AI.

Run from the project root:   .venv\\Scripts\\python -m datagen.generate
Writes CSVs to data/ (one per DB table) and evaluation-only files to data/_ground_truth/.
"""
from __future__ import annotations

import math
import random
import re
import string
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog_certs import CERT_IDS, CERTS
from .catalog_clients import CLIENTS, INDUSTRY_NAMES
from .catalog_names import DEGREES, FAMILY_DEGREE, LOCATION_MIX, LOCATION_WEIGHTS, NAME_POOLS
from .catalog_projects import ARCHETYPES
from .catalog_skills import FAMILIES, LEVELS, SKILL_NAMES, SKILLS

SEED = 17
TODAY = date(2026, 10, 26)          # snapshot date of the dataset
HISTORY_START = date(2019, 1, 1)
COMPANY = "Nexora Technologies Pvt. Ltd."
EMAIL_DOMAIN = "nexoratech.example"  # reserved TLD: synthetic addresses can never reach a real inbox
N_EMPLOYEES = 1450          # everyone who worked at Nexora since mid-2018; ~55% are current employees
EXIT_RATE = 0.45
PROJECT_STARTS_PER_HEAD = 0.21   # new project starts per employee per year (keeps utilisation ~80-85%)
N_PIPELINE = 30
N_OPEN_DEMANDS = 16

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data"
GT = OUT / "_ground_truth"

rng = random.Random(SEED)
np.random.seed(SEED)


# ----------------------------------------------------------------------------- helpers
def D(s):
    return date.fromisoformat(s) if isinstance(s, str) else s


def add_days(d, n):
    return d + timedelta(days=int(round(n)))


def add_months(d, m):
    return add_days(d, m * 30.44)


def years_between(a, b):
    return (b - a).days / 365.25


def rand_date(a, b):
    if b <= a:
        return a
    return a + timedelta(days=rng.randint(0, (b - a).days))


def wchoice(weights: dict):
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def iso(d):
    return d.isoformat() if d else None


def _alnum(n, chars=string.ascii_uppercase + string.digits):
    return "".join(rng.choice(chars) for _ in range(n))


def _digits(n):
    return "".join(rng.choice(string.digits) for _ in range(n))


def _uuid():
    h = "".join(rng.choice("0123456789abcdef") for _ in range(32))
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


CREDENTIAL_FORMATS = {
    "Amazon Web Services": lambda: _alnum(16),
    "Microsoft": lambda: f"{_alnum(6, '0123456789ABCDEF')}-{_alnum(6, '0123456789ABCDEF')}",
    "Google Cloud": _uuid,
    "The Linux Foundation (CNCF)": lambda: "LF-" + _alnum(10, string.ascii_lowercase + string.digits),
    "HashiCorp": _uuid,
    "Red Hat": lambda: f"{_digits(3)}-{_digits(3)}-{_digits(3)}",
    "Databricks": lambda: _digits(8),
    "Snowflake": _uuid,
    "Salesforce (Tableau)": _uuid,
    "Oracle": lambda: "OC" + _digits(7),
    "Salesforce": lambda: "SF-" + _digits(7),
    "Project Management Institute (PMI)": lambda: _digits(7),
    "Scrum Alliance": lambda: "000" + _digits(7),
    "Scrum.org": lambda: _digits(6),
    "Scaled Agile, Inc.": lambda: _digits(8),
    "PeopleCert (AXELOS)": lambda: "GR" + _digits(9),
    "ISTQB": lambda: "ITB-" + _digits(6),
    "CompTIA": lambda: "COMP001" + _digits(9),
    "EC-Council": lambda: "ECC" + _digits(10),
    "ISC2": lambda: _digits(6),
    "Google (Coursera)": lambda: _alnum(12),
    "Nielsen Norman Group": lambda: "UXC-" + _digits(6),
    "IIBA": lambda: _digits(6),
}


# ----------------------------------------------------------------------------- validation of catalogs
def validate_catalogs():
    problems = []
    for fam, f in FAMILIES.items():
        for _, _, core, tcerts in f["tracks"]:
            problems += [f"{fam} core:{s}" for s in core if s not in SKILL_NAMES]
            problems += [f"{fam} track cert:{c}" for c in tcerts if c not in CERT_IDS]
        problems += [f"{fam} common:{s}" for s in f["common"] + f["occasional"] if s not in SKILL_NAMES]
        problems += [f"{fam} cert:{c}" for c in f["certs"] if c not in CERT_IDS]
    for c in CERTS:
        problems += [f"cert {c['cert_id']} skill:{s}" for s in c["skills"] if s not in SKILL_NAMES]
    for a in ARCHETYPES:
        problems += [f"{a['key']} domain:{s}" for s in a["domain_skills"] if s not in SKILL_NAMES]
        for r in a["roles"]:
            if r["family"] not in FAMILIES:
                problems.append(f"{a['key']} family {r['family']}")
            for s in r["must"] + r["nice"]:
                if s.split(":")[0] not in SKILL_NAMES:
                    problems.append(f"{a['key']}/{r['title']} skill:{s}")
            problems += [f"{a['key']}/{r['title']} cert:{c}" for c in r["certs"] + r["mcerts"] if c not in CERT_IDS]
    if problems:
        raise ValueError("Catalog references unknown items:\n  " + "\n  ".join(problems))


# ----------------------------------------------------------------------------- reference tables
SKILL_ID = {}
SKILL_META = {}
CERT = {c["cert_id"]: c for c in CERTS}


def build_reference():
    skills, aliases = [], []
    for i, (name, cat, al, since) in enumerate(SKILLS, start=1):
        sid = f"SK{i:03d}"
        SKILL_ID[name] = sid
        SKILL_META[name] = dict(category=cat, since=since)
        skills.append(dict(skill_id=sid, skill_name=name, category=cat, available_since_year=since))
        aliases += [dict(skill_id=sid, alias=a) for a in al]
    certs, cert_skills = [], []
    for c in CERTS:
        certs.append(dict(cert_id=c["cert_id"], cert_name=c["name"], vendor=c["vendor"], exam_code=c["exam_code"],
                          level=c["level"], validity_months=c["validity_months"],
                          available_from=c["available_from"], retired_on=c.get("retired_on")))
        cert_skills += [dict(cert_id=c["cert_id"], skill_id=SKILL_ID[s]) for s in c["skills"]]
    clients = [dict(client_id=code, client_name=name, industry=INDUSTRY_NAMES[ind], industry_code=ind,
                    sub_industry=sub, hq_city=city, country=country, relationship_since=since)
               for code, name, ind, sub, city, country, since, _ in CLIENTS]
    return skills, aliases, certs, cert_skills, clients


# ----------------------------------------------------------------------------- employees
def pick_name(location, gender):
    region = wchoice(LOCATION_MIX[location])
    pool = NAME_POOLS[region]
    first = rng.choice(pool["male" if gender == "Male" else "female"])
    override = pool.get("female_surname_override" if gender == "Female" else "male_surname_override")
    if override and rng.random() < override[1]:
        last = override[0]
    else:
        last = rng.choice(pool["surnames"])
    return first, last


def make_email(first, last, used):
    base = re.sub(r"[^a-z.]", "", f"{first}.{last}".lower().replace(" ", ""))
    email, k = f"{base}@{EMAIL_DOMAIN}", 1
    while email in used:
        k += 1
        email = f"{base}{k}@{EMAIL_DOMAIN}"
    used.add(email)
    return email


def pick_level(family):
    if family == "pm":
        return wchoice({3: .25, 4: .38, 5: .25, 6: .12})
    weights = {lv: LEVELS[lv]["weight"] for lv in LEVELS}
    if family in ("ux", "security", "salesforce", "ba"):
        weights[6] = 0.01
    return wchoice(weights)


def gen_employees():
    fam_weights = {k: v["share"] for k, v in FAMILIES.items()}
    used_emails, emps = set(), []
    for _ in range(N_EMPLOYEES):
        fam_key = wchoice(fam_weights)
        fam = FAMILIES[fam_key]
        level = pick_level(fam_key)
        exited = rng.random() < EXIT_RATE
        exit_date = None
        if exited:   # attrition peaked in the 2021-22 "great resignation" across Indian IT
            y = wchoice({2018: .04, 2019: .10, 2020: .08, 2021: .15, 2022: .18, 2023: .14, 2024: .12, 2025: .12, 2026: .07})
            exit_date = rand_date(max(date(y, 1, 1), date(2018, 7, 1)), min(date(y, 12, 31), add_days(TODAY, -25)))
        ref = exit_date or TODAY
        lo, hi = LEVELS[level]["exp"]
        exp_ref = round(rng.triangular(lo, hi, lo + (hi - lo) * 0.4), 1)
        if level == 1 and rng.random() < 0.8:
            tenure = exp_ref
        elif exited:   # leavers typically leave after 1-4 years (Indian IT attrition pattern)
            tenure = min(exp_ref, max(0.5, rng.expovariate(1 / 3.0)))
        elif rng.random() < 0.6:
            tenure = rng.uniform(0.3, min(exp_ref, 15))
        else:
            tenure = min(exp_ref, max(0.1, rng.expovariate(1 / 4.0)))
        join = add_days(ref, -tenure * 365.25)
        if join < date(2010, 1, 4):
            join = rand_date(date(2010, 1, 4), date(2012, 12, 31))
            tenure = years_between(join, ref)
            exp_ref = max(exp_ref, round(tenure, 1))
        join = join if join.weekday() < 5 else add_days(join, 7 - join.weekday())  # joins happen on weekdays
        prior = round(max(0.0, exp_ref - years_between(join, ref)), 1)
        gender = "Female" if rng.random() < fam["female_share"] else "Male"
        location = wchoice(LOCATION_WEIGHTS)
        first, last = pick_name(location, gender)
        track = rng.choices(fam["tracks"], weights=[t[0] for t in fam["tracks"]], k=1)[0]
        degree = rng.choices(*zip(*DEGREES[FAMILY_DEGREE.get(fam_key, "engineering")]), k=1)[0]
        pg = any(k in degree for k in ("M.", "MCA", "MBA", "M.Des"))
        brk = 0
        if gender == "Female" and rng.random() < 0.13:
            brk = rng.randint(6, 26)
        elif gender == "Male" and rng.random() < 0.03:
            brk = rng.randint(3, 12)
        age_ref = exp_ref + rng.uniform(21.3, 23.0) + (2 if pg else 0) + brk / 12
        dob = add_days(ref, -age_ref * 365.25)
        emps.append(dict(
            family=fam_key, level=level, track=track, primary_skill=track[1], first=first, last=last,
            full_name=f"{first} {last}", gender=gender, location=location, join=join, exit=exit_date,
            prior_exp=prior, exp_ref=exp_ref, dob=dob, degree=degree, career_break=brk,
            ability=rng.gauss(0, 1), email=make_email(first, last, used_emails),
            work_mode=wchoice({"Hybrid": .78, "Work from Office": .14, "Remote": .08}),
            status="Exited" if exited else "Active",
        ))
    emps.sort(key=lambda e: (e["join"], e["full_name"]))
    for i, e in enumerate(emps):
        e["id"] = f"NXT{10001 + i}"
        e["designation"] = FAMILIES[e["family"]]["titles"][e["level"] - 1]
    return emps


def exp_at(e, d):
    if d < e["join"]:
        return e["prior_exp"]
    return e["prior_exp"] + years_between(e["join"], d)


def employed_on(e, d):
    return e["join"] <= d and (e["exit"] is None or e["exit"] >= d)


# ----------------------------------------------------------------------------- skills & certs
BASE_PROF = {1: 2.1, 2: 2.8, 3: 3.4, 4: 3.8, 5: 4.1, 6: 3.9}


def skill_years_cap(e, skill):
    ref = e["exit"] or TODAY
    career_start = add_days(ref, -e["exp_ref"] * 365.25)
    since = SKILL_META[skill]["since"]
    start = max(career_start, date(since, 1, 1)) if since else career_start
    return max(0.0, years_between(start, ref))


def gen_skills(e):
    fam = FAMILIES[e["family"]]
    core = list(dict.fromkeys(e["track"][2]))
    skills = {}

    def add(skill, tier):
        if skill in skills:
            return
        ref = e["exit"] or TODAY
        since = SKILL_META[skill]["since"]
        if since and ref.year < since:
            return
        bump = {"core": 0.35, "common": -0.2, "occasional": -0.75, "background": -1.0}[tier]
        p = BASE_PROF[e["level"]] + bump + 0.35 * e["ability"] + rng.gauss(0, 0.55)
        cap = skill_years_cap(e, skill)
        frac = {"core": (0.6, 1.0), "common": (0.2, 0.8), "occasional": (0.1, 0.5), "background": (0.3, 0.9)}[tier]
        yrs = round(max(0.5, cap * rng.uniform(*frac)) * 2) / 2
        yrs = min(yrs, max(0.5, round(cap * 2) / 2))
        if cap < 1.0:
            p = min(p, 3)
        career_start = add_days(ref, -e["exp_ref"] * 365.25)
        acquired = max(add_days(career_start, -365), add_days(ref, -yrs * 365.25 - rng.randint(0, 150)))
        skills[skill] = dict(prof=int(clip(round(p), 1, 5)), years=yrs, acquired=acquired,
                             verified=rng.random() < (0.65 if tier == "core" else 0.45))

    for s in core:
        if rng.random() < 0.94:
            add(s, "core")
    for s in fam["common"]:
        if rng.random() < 0.42:
            add(s, "common")
    for s in fam["occasional"]:
        if rng.random() < 0.12:
            add(s, "occasional")
    if e["family"] in ("pm", "ba") and rng.random() < 0.6:   # delivery folks usually came from engineering
        bg = FAMILIES[rng.choice(["java", "dotnet", "qa", "data_eng"])]["tracks"][0][2]
        for s in rng.sample(bg, 2):
            add(s, "background")
    return skills


def cert_validity(cert, issue):
    v = cert["validity_months"]
    if v and cert["cert_id"] in ("CKA", "CKAD") and issue < date(2024, 4, 1):
        v = 36
    return v


def gen_certs(e):
    fam = FAMILIES[e["family"]]
    probs = dict(fam["certs"])
    for c, p in e["track"][3].items():
        probs[c] = max(probs.get(c, 0), p)
    level_factor = {1: 0.45, 2: 0.9, 3: 1.2, 4: 1.3, 5: 1.2, 6: 1.0}[e["level"]]
    ref = e["exit"] or TODAY
    career_start = add_days(ref, -e["exp_ref"] * 365.25)
    out = []
    for cid, p in probs.items():
        cert = CERT[cid]
        if e["level"] < cert.get("min_level", 1) or rng.random() > min(0.9, 1.7 * p * level_factor):
            continue
        earliest = max(D(cert["available_from"]), add_days(career_start, 120))
        latest = min(ref, D(cert["retired_on"]) if cert.get("retired_on") else ref)
        if earliest >= latest:
            continue
        # people mostly certify in recent years; skew towards the later part of the window
        span = (latest - earliest).days
        issue = add_days(earliest, span * (1 - rng.random() ** 1.8))
        out.append(make_cert_record(e, cert, issue))
    return out


def make_cert_record(e, cert, issue):
    ref = e["exit"] or TODAY
    validity = cert_validity(cert, issue)
    expiry, renewed = None, None
    if validity:
        expiry = add_months(issue, validity)
        renew_p = 0.72 if cert["vendor"] == "Microsoft" else 0.5
        retired = D(cert["retired_on"]) if cert.get("retired_on") else None
        while expiry < ref and rng.random() < renew_p and (retired is None or expiry < retired):
            renewed = add_days(expiry, -rng.randint(5, 150))
            expiry = add_months(expiry, validity)
    return dict(cert_id=cert["cert_id"], issue=issue, expiry=expiry, renewed=renewed,
                credential=CREDENTIAL_FORMATS[cert["vendor"]](),
                verification="Verified" if rng.random() < 0.86 else "Pending Verification")


def cert_valid_on(c, d):
    return c["issue"] <= d and (c["expiry"] is None or c["expiry"] >= d)


# ----------------------------------------------------------------------------- projects
def default_min_prof(skill, exp):
    if SKILL_META[skill]["category"] == "Domain":
        return 2
    return 2 if exp < 3 else (3 if exp < 7 else 4)


def parse_skill(s, exp):
    name, _, lvl = s.partition(":")
    return name, int(lvl) if lvl else default_min_prof(name, exp)


def fmt_desc(tpl, client, vars_):
    vals = {k: rng.choice(v) for k, v in vars_.items()}
    return tpl.format(client=client["client_name"], **vals)


def build_roles(arch, proj):
    roles = []
    for spec in arch["roles"]:
        n = rng.randint(*spec["n"])
        if proj["priority"] == "Critical" and spec["n"][1] > 1 and rng.random() < 0.4:
            n += 1
        start = add_months(proj["start"], spec["ramp"])
        if start >= proj["end"]:
            start = proj["start"]
        must = [parse_skill(s, spec["exp"]) for s in spec["must"]]
        nice = [s.split(":")[0] for s in spec["nice"]]
        if nice and rng.random() < 0.25:
            nice.remove(rng.choice(nice))
        if rng.random() < 0.2:
            extra = rng.choice(FAMILIES[spec["family"]]["common"])
            if extra not in nice and extra not in [m[0] for m in must]:
                nice.append(extra)
        alloc = spec["alloc"]
        small_team = sum(r["n"][0] for r in arch["roles"]) <= 7
        if small_team and alloc == 100 and spec["family"] in ("qa", "devops", "ux", "ba", "security") and rng.random() < 0.5:
            alloc = 50   # shared specialists split across small engagements
        roles.append(dict(title=spec["title"], family=spec["family"], headcount=n, min_exp=spec["exp"],
                          alloc=alloc, start=start, end=proj["end"], must=must, nice=nice,
                          certs=list(spec["certs"]), mcerts=list(spec["mcerts"]), demand_type="Initial"))
    # project pyramid: larger teams carry 1-2 associate engineers (0-2 yrs) shadowing the junior delivery role
    junior = [r for r in roles if r["family"] in ASSOCIATE_TITLES and r["min_exp"] <= 2 and r["alloc"] == 100]
    if junior and sum(r["headcount"] for r in roles) >= 6 and rng.random() < 0.65:
        base = junior[0]
        roles.append(dict(base, title=ASSOCIATE_TITLES[base["family"]], headcount=rng.choice([1, 1, 2]), min_exp=0,
                          must=[(n, 2) for n, _ in base["must"][:2]], nice=[n for n, _ in base["must"][2:]] + base["nice"][:2],
                          certs=[], mcerts=[]))
    return roles


ASSOCIATE_TITLES = {"java": "Associate Software Engineer", "dotnet": "Associate Software Engineer",
                    "python": "Associate Software Engineer", "fullstack": "Associate Software Engineer",
                    "frontend": "Associate Software Engineer", "data_eng": "Associate Data Engineer",
                    "qa": "Associate QA Engineer", "mobile": "Associate Mobile Developer"}


def gen_projects(clients, emps):
    client_by_code = {c["client_id"]: c for c in clients}
    weights = {c[0]: c[7] for c in CLIENTS}
    plan = []
    for year in range(2018, TODAY.year + 1):
        mid = date(year, 7, 1)
        headcount = sum(1 for e in emps if employed_on(e, mid))
        months = 7 if year == 2018 else (TODAY.month if year == TODAY.year else 12)
        plan.append((year, round(headcount * PROJECT_STARTS_PER_HEAD * months / 12)))
    projects, seq = [], Counter()

    def make(start, pipeline=False):
        year = start.year
        eligible_clients = {k: w for k, w in weights.items() if client_by_code[k]["relationship_since"] <= year}
        for _ in range(40):
            code = wchoice(eligible_clients)
            client = client_by_code[code]
            ind = client["industry_code"]
            cands = [a for a in ARCHETYPES if ind in a["industries"] and a["since"] <= max(year, 2019)]
            w = [1.0 if len(a["industries"]) < 6 else 0.45 for a in cands]
            arch = rng.choices(cands, weights=w, k=1)[0]
            same = [p for p in projects if p["client_id"] == code and p["arch"] is arch]
            if not any(p["end"] >= start for p in same) and len(same) < 3:
                break
        prior = [p for p in projects if p["client_id"] == code and p["arch"] is arch]
        name = rng.choice(arch["names"])
        if prior:
            name = f"{prior[0]['name'].split(' – Phase')[0]} – Phase {len(prior) + 1}"
        months = rng.randint(*arch["months"])
        end = add_months(start, months)
        status = "Pipeline" if pipeline else ("Completed" if end < TODAY else "Active")
        seq[(code, year)] += 1
        proj = dict(
            arch=arch, name=name, client_id=code, client=client, industry=client["industry"],
            code=f"{code}-{str(year)[2:]}-{seq[(code, year)]:02d}{rng.choice('0123456789')}",
            ptype=arch["ptype"], engagement=rng.choice(arch["engagement"]), start=start, end=end, status=status,
            priority=wchoice({"Critical": .10, "High": .35, "Medium": .45, "Low": .10}),
            location=client["hq_city"] if client["hq_city"] in LOCATION_WEIGHTS and rng.random() < 0.7
            else wchoice(LOCATION_WEIGHTS),
            description=fmt_desc(rng.choice(arch["desc"]), client, arch["vars"]),
            created_on=add_days(start, -rng.randint(10, 60)),
        )
        if prior:
            proj["description"] += f" This phase builds on the earlier engagement ({prior[-1]['code']})."
        proj["roles"] = build_roles(arch, proj)
        projects.append(proj)

    for year, n in plan:
        lo = date(year, 6, 1) if year == 2018 else date(year, 1, 2)   # 2018 H2 only: warm-up so 2019 is not empty
        hi = min(date(year, 12, 20), add_days(TODAY, -3))
        for _ in range(n):
            make(rand_date(lo, hi))
    for _ in range(N_PIPELINE):
        make(add_days(TODAY, rng.randint(9, 115)), pipeline=True)
    projects.sort(key=lambda p: p["start"])
    for i, p in enumerate(projects, start=1):
        p["id"] = f"PRJ{i:04d}"
    return projects


# ----------------------------------------------------------------------------- staffing simulation
class Staffing:
    def __init__(self, emps, projects):
        self.emps = emps
        self.by_family = defaultdict(list)
        for e in emps:
            self.by_family[e["family"]].append(e)
        self.projects = projects
        self.assignments = []
        self.intervals = defaultdict(list)   # emp id -> [(start, end, alloc, assignment index)]
        self.history = defaultdict(list)     # emp id -> [(start, industry)]

    def load_at(self, eid, d):
        return sum(a for s, e, a, _ in self.intervals[eid] if s <= d <= e)

    def max_load(self, eid, s, e):
        pts = {s} | {iv[0] for iv in self.intervals[eid] if s <= iv[0] <= e}
        return max(self.load_at(eid, p) for p in pts)

    def n_projects_at(self, eid, d):
        return sum(1 for s, e, a, _ in self.intervals[eid] if s <= d <= e)

    def candidates(self, role, s, e, cap):
        fams = [role["family"]] + FAMILIES[role["family"]]["alt_families"]
        out = []
        for fam in fams:
            for emp in self.by_family[fam]:
                if emp["join"] > add_days(s, -7) or (emp["exit"] and emp["exit"] < add_days(s, 30)):
                    continue
                if exp_at(emp, s) < role["min_exp"] - 1:
                    continue
                if role["family"] == "pm" and emp["level"] < 3:
                    continue
                if self.max_load(emp["id"], s, e) + role["alloc"] > cap:
                    continue
                if self.n_projects_at(emp["id"], s) >= (4 if role["family"] == "pm" else 3):
                    continue
                out.append((emp, fam != role["family"]))
        return out

    def score(self, emp, alt, role, proj, s):
        sk = emp["skills"]
        must = [min(sk[n]["prof"] / mp, 1.2) if n in sk else 0.0 for n, mp in role["must"]]
        must_m = sum(must) / len(must) if must else 1.0
        nice_m = sum(1 for n in role["nice"] if n in sk) / len(role["nice"]) if role["nice"] else 0.0
        xp = exp_at(emp, s)
        level_fit = -abs(xp - (role["min_exp"] + 2.5)) / 4
        domain = min(1.0, sum(1 for d0, ind in self.history[emp["id"]] if ind == proj["industry"] and d0 < s) / 3)
        cur = self.load_at(emp["id"], s)
        if role["alloc"] >= 100:
            idle = 0.6 if cur == 0 else 0.0           # full-time roles go to bench people first
        else:
            idle = 0.7 if 0 < cur and cur + role["alloc"] <= 100 else 0.0   # partial roles fill spare partial capacity
        loc = 0.3 if emp["location"] == proj["location"] else 0.0
        sc = (2.2 * must_m + 0.6 * nice_m + 0.5 * level_fit + 0.5 * domain + idle + loc
              - (0.8 if alt else 0.0) + rng.gauss(0, 0.5))
        return sc, dict(must_match=round(must_m, 3), nice_match=round(nice_m, 3), domain_prior=round(domain, 3))

    def staff_segment(self, proj, role, role_id, s, e, reason_end):
        stretch = rng.random() < 0.10
        pool = self.candidates(role, s, e, 150 if stretch else 100)
        if not pool and not stretch:
            pool = self.candidates(role, s, e, 150)
        if not pool:
            return None
        scored = [(self.score(emp, alt, role, proj, s), emp) for emp, alt in pool]
        (sc, feats), emp = max(scored, key=lambda t: t[0][0])
        end, release = e, reason_end
        if emp["exit"] and emp["exit"] < e:
            end, release = emp["exit"], "Resigned"
        status = "Completed" if end < TODAY else ("Upcoming" if s > TODAY else "Active")
        idx = len(self.assignments)
        self.assignments.append(dict(
            employee_id=emp["id"], project_id=proj["id"], project_role_id=role_id, role_title=role["title"],
            allocation_pct=role["alloc"], start=s, end=end, status=status,
            billable=rng.random() > 0.06, assigned_by=None, assigned_on=add_days(s, -rng.randint(3, 25)),
            release_reason=release if status == "Completed" else None, feats=feats, proj=proj, role=role,
        ))
        self.intervals[emp["id"]].append((s, end, role["alloc"], idx))
        self.history[emp["id"]].append((s, proj["industry"]))
        if end < e and release == "Resigned":
            gap_start = add_days(end, rng.randint(7, 30))
            if gap_start < e:
                self.staff_segment(proj, role, role_id, gap_start, e, reason_end)
        return emp

    def run(self, role_rows):
        """role_rows: list of (proj, role, role_id). Staffs everything that starts on/before TODAY plus PMs of
        pipeline projects; open demands and other pipeline roles stay unfilled for the demo."""
        order = sorted(role_rows, key=lambda t: (t[1]["start"], t[1]["family"] != "pm"))
        for proj, role, role_id in order:
            if role["demand_type"] != "Initial":
                continue
            if proj["status"] == "Pipeline" and role["family"] != "pm":
                continue
            for _ in range(role["headcount"]):
                s, e = role["start"], role["end"]
                if (e - s).days > 300 and rng.random() < 0.35:
                    cut = add_days(s, (e - s).days * rng.uniform(0.3, 0.7))
                    reason = rng.choice(["Rotated to another project", "Client ramp-down", "Role completed",
                                         "Moved to internal initiative"])
                    self.staff_segment(proj, role, role_id, s, cut, reason)
                    self.staff_segment(proj, role, role_id, add_days(cut, rng.randint(1, 20)), e, "Project completed")
                else:
                    self.staff_segment(proj, role, role_id, s, e, "Project completed")
            if role["family"] == "pm" and "pm_id" not in proj:
                pm = [a for a in self.assignments if a["project_role_id"] == role_id]
                if pm:
                    proj["pm_id"] = pm[0]["employee_id"]

    def rebuild_intervals(self):
        self.intervals = defaultdict(list)
        for i, a in enumerate(self.assignments):
            self.intervals[a["employee_id"]].append((a["start"], a["end"], a["allocation_pct"], i))


# ----------------------------------------------------------------------------- ratings & feedback
FEEDBACK = {
    5: ["Outstanding contribution - owned the {skill} work end-to-end and became the go-to person for the team.",
        "Exceeded expectations on {project}; delivered critical {skill} components ahead of schedule with very few defects.",
        "Client explicitly appreciated their {skill} work in the steering committee; also mentored two juniors.",
        "Exceptional ownership during go-live; resolved production issues quickly and documented fixes well."],
    4: ["Strong performer; delivered {skill} stories reliably with good quality and minimal rework.",
        "Consistently met sprint commitments and handled UAT feedback calmly. Solid {skill} skills.",
        "Good ownership and clear communication with client stakeholders.",
        "Dependable team member; contributed useful improvements to the {skill} codebase and reviews."],
    3: ["Met expectations. Delivered the assigned {skill} work with some guidance.",
        "Reliable team member; should improve estimation and proactive status communication.",
        "Completed tasks on time; needs to deepen hands-on {skill} expertise for senior-level work.",
        "Satisfactory delivery. Took a few sprints to ramp up on the domain."],
    2: ["Below expectations - needed frequent support on {skill} tasks and defect leakage was high.",
        "Struggled to ramp up on the {skill} stack; two sprint commitments slipped.",
        "Needs to improve ownership and code quality; a development plan was agreed."],
    1: ["Did not meet expectations; released early after repeated quality issues.",
        "Significant gaps in {skill}; most of the assigned tasks had to be reassigned."],
}
OVERLOAD_NOTE = " Was stretched across multiple engagements, which affected availability in critical phases."


def rate_assignments(st, emps_by_id, latent_rows):
    lat = []
    for i, a in enumerate(st.assignments):
        if a["status"] != "Completed" or (a["end"] - a["start"]).days < 45:
            continue
        e = emps_by_id[a["employee_id"]]
        role = a["role"]
        overload = st.max_load(e["id"], a["start"], a["end"]) > 100
        xp = exp_at(e, a["start"])
        exp_fit = clip((xp - role["min_exp"]) / 3, -1, 1)
        certs_wanted = set(role["certs"] + role["mcerts"])
        cert_match = 1.0 if any(c["cert_id"] in certs_wanted and cert_valid_on(c, a["start"]) for c in e["certs"]) else 0.0
        age = years_between(e["dob"], a["start"])
        bias = (-0.30 if e["gender"] == "Female" else 0) + (-0.20 if age >= 45 else 0) + (-0.15 if e["career_break"] else 0)
        noise = rng.gauss(0, 0.6)
        z = (1.2 * a["feats"]["must_match"] + 0.4 * a["feats"]["nice_match"] + 0.5 * exp_fit
             + 0.5 * a["feats"]["domain_prior"] + 0.25 * cert_match - 0.6 * overload + 0.5 * e["ability"] + noise)
        a["overloaded"] = overload
        lat.append((i, z + bias, z, bias, exp_fit, cert_match, overload, noise))
    zs = np.array([t[1] for t in lat])
    cuts = np.quantile(zs, [0.03, 0.13, 0.55, 0.89])
    for i, zb, z, bias, exp_fit, cert_match, overload, noise in lat:
        rating = 1 + int(np.searchsorted(cuts, zb))
        st.assignments[i]["performance_rating"] = rating
        a = st.assignments[i]
        a["_latent"] = len(latent_rows)
        latent_rows.append(dict(assignment_id=None, must_skill_match=a["feats"]["must_match"],
                                preferred_skill_match=a["feats"]["nice_match"], domain_familiarity=a["feats"]["domain_prior"],
                                experience_fit=round(exp_fit, 3), cert_match=cert_match, overloaded=overload,
                                employee_ability=round(emps_by_id[a["employee_id"]]["ability"], 3),
                                noise=round(noise, 3), injected_bias=round(bias, 3),
                                latent_unbiased=round(z, 3), latent_with_bias=round(zb, 3), rating=rating))


# ----------------------------------------------------------------------------- main
def main():
    validate_catalogs()
    OUT.mkdir(exist_ok=True)
    GT.mkdir(exist_ok=True)
    skills_ref, aliases, certs_ref, cert_skills, clients = build_reference()

    emps = gen_employees()
    by_id = {e["id"]: e for e in emps}
    for e in emps:
        e["skills"] = gen_skills(e)
        e["certs"] = gen_certs(e)

    projects = gen_projects(clients, emps)
    role_rows, rid = [], 0
    for p in projects:
        for r in p["roles"]:
            rid += 1
            r["id"] = f"PR{rid:05d}"
            role_rows.append((p, r, r["id"]))

    # open demands (ramp-ups / backfills) on running projects
    running = [p for p in projects if p["status"] == "Active" and p["end"] > add_days(TODAY, 150)]
    for p in rng.sample(running, min(N_OPEN_DEMANDS, len(running))):
        base = rng.choice([r for r in p["roles"] if r["family"] != "pm"])
        extra = dict(base, headcount=rng.choice([1, 1, 1, 2]), start=add_days(TODAY, rng.randint(7, 45)),
                     demand_type=rng.choice(["Ramp-up", "Backfill"]))
        rid += 1
        extra["id"] = f"PR{rid:05d}"
        p["roles"].append(extra)
        role_rows.append((p, extra, extra["id"]))

    # account delivery managers (senior PMs own client accounts)
    dms = [e for e in emps if e["family"] == "pm" and e["level"] >= 5 and e["status"] == "Active"]
    client_dm = {c["client_id"]: rng.choice(dms)["id"] for c in clients}

    st = Staffing(emps, projects)
    st.run(role_rows)
    for p in projects:
        p["dm_id"] = client_dm[p["client_id"]]
        p.setdefault("pm_id", p["dm_id"])
    for a in st.assignments:
        p = a["proj"]
        a["assigned_by"] = p["dm_id"] if a["employee_id"] == p["pm_id"] else p["pm_id"]

    # ---- skills grow through project work (this is the "evidence" trail)
    domain_count = defaultdict(Counter)
    domain_first = defaultdict(dict)   # first date domain knowledge was gained (end of first project in it)
    for a in sorted(st.assignments, key=lambda x: x["start"]):
        if a["start"] > TODAY:
            continue
        e = by_id[a["employee_id"]]
        months = (min(a["end"], TODAY) - a["start"]).days / 30.4
        learned_on = min(TODAY, add_days(a["start"], rng.randint(10, 45)))
        # skills the person was staffed for were held before the project started
        for name in [n for n, _ in a["role"]["must"]] + a["role"]["nice"]:
            cur = e["skills"].get(name)
            if cur and cur["acquired"] > a["start"]:
                cur["acquired"] = add_days(a["start"], -rng.randint(15, 200))
        for name, mp in a["role"]["must"]:
            if name not in e["skills"] and rng.random() < 0.55:
                e["skills"][name] = dict(prof=2 + (months > 12), years=round(max(0.5, months / 12) * 2) / 2,
                                         verified=rng.random() < 0.5, acquired=learned_on)
            elif name in e["skills"] and e["skills"][name]["prof"] < 5 and rng.random() < 0.15:
                e["skills"][name]["prof"] += 1
        for name in a["role"]["nice"]:
            if name not in e["skills"] and rng.random() < 0.2:
                e["skills"][name] = dict(prof=2, years=round(max(0.5, months / 12) * 2) / 2, verified=False,
                                         acquired=learned_on)
        for ds in a["proj"]["arch"]["domain_skills"]:
            domain_count[e["id"]][ds] += 1
            domain_first[e["id"]].setdefault(ds, min(a["end"], TODAY))
        for name in [n for n, _ in a["role"]["must"]] + a["role"]["nice"] + a["proj"]["arch"]["domain_skills"]:
            if name in e["skills"]:
                e["skills"][name]["last_used"] = max(e["skills"][name].get("last_used", date.min), min(a["end"], TODAY))
    for eid, cnt in domain_count.items():
        e = by_id[eid]
        for ds, k in cnt.items():
            if rng.random() < (0.55 if k == 1 else 0.85):
                cur = e["skills"].get(ds)
                prof = min(5, 1 + k + (rng.random() < 0.3))
                if not cur or cur["prof"] < prof:
                    acquired = min(cur["acquired"], domain_first[eid][ds]) if cur else domain_first[eid][ds]
                    e["skills"][ds] = dict(prof=prof, years=round(max(0.5, k * 0.8) * 2) / 2, verified=rng.random() < 0.6,
                                           last_used=(cur or {}).get("last_used"), acquired=acquired)

    # ---- notice periods, long leave, planned leave
    active = [e for e in emps if e["status"] == "Active"]
    leaves = []
    for e in rng.sample([x for x in active if x["family"] != "pm"], int(len(active) * 0.03)):
        e["status"] = "Serving Notice"
        e["exit"] = add_days(TODAY, rng.randint(15, 85))
        for a in st.assignments:
            if a["employee_id"] == e["id"] and a["end"] > e["exit"]:
                a["end"], a["release_reason"] = e["exit"], "Resigned - serving notice"
    st.rebuild_intervals()
    bench_now = [e for e in active if e["status"] == "Active" and st.load_at(e["id"], TODAY) == 0 and e["join"] < add_days(TODAY, -120)]
    for e in rng.sample(bench_now, min(9, len(bench_now))):
        e["status"] = "On Long Leave"
        if e["gender"] == "Female" and rng.random() < 0.6:
            s = add_days(TODAY, -rng.randint(10, 120))
            leaves.append(dict(employee_id=e["id"], leave_type="Maternity Leave", start=s, end=add_days(s, 182), status="Approved"))
        else:
            s = add_days(TODAY, -rng.randint(5, 40))
            leaves.append(dict(employee_id=e["id"], leave_type=rng.choice(["Medical Leave", "Sabbatical"]), start=s,
                               end=add_days(s, rng.randint(45, 120)), status="Approved"))
    for e in [x for x in active if x["status"] == "Active"]:
        if rng.random() > 0.13:
            continue
        kind = wchoice({"Earned Leave": .68, "Sick Leave": .08, "Paternity Leave": .07 if e["gender"] == "Male" else 0,
                        "Maternity Leave": .06 if e["gender"] == "Female" else 0, "Marriage Leave": .05,
                        "Sabbatical": .01})
        s = add_days(TODAY, rng.randint(-4, 150))
        length = {"Earned Leave": rng.randint(4, 15), "Sick Leave": rng.randint(2, 5), "Paternity Leave": 15,
                  "Maternity Leave": 182, "Marriage Leave": rng.randint(7, 12), "Sabbatical": rng.randint(60, 120)}[kind]
        leaves.append(dict(employee_id=e["id"], leave_type=kind, start=s, end=add_days(s, length - 1),
                           status="Approved" if s < add_days(TODAY, 30) or rng.random() < 0.7 else "Pending"))
        if length > 30:   # long leave: release from projects beforehand
            for a in st.assignments:
                if a["employee_id"] == e["id"] and a["end"] >= s and a["start"] <= TODAY:
                    a["end"], a["release_reason"] = add_days(s, -1), f"Released ahead of {kind.lower()}"
    # an upcoming assignment that would start after the person's exit/leave is simply never made
    st.assignments = [a for a in st.assignments if a["end"] >= a["start"]]
    for p in projects:
        if not any(a["employee_id"] == p["pm_id"] and a["project_id"] == p["id"] for a in st.assignments):
            p["pm_id"] = p["dm_id"]
    st.rebuild_intervals()
    for a in st.assignments:
        a["status"] = "Completed" if a["end"] < TODAY else ("Upcoming" if a["start"] > TODAY else "Active")
        if a["status"] != "Completed":
            a["release_reason"] = None if a["release_reason"] in (None, "Project completed") or a["end"] > TODAY else a["release_reason"]

    latent_rows = []
    rate_assignments(st, by_id, latent_rows)

    # ---- demo coverage: every open demand must have a healthy shortlist
    long_leave = defaultdict(list)
    for lv in leaves:
        if (lv["end"] - lv["start"]).days > 10 and lv["status"] == "Approved":
            long_leave[lv["employee_id"]].append((lv["start"], lv["end"]))

    def available(e, d, alloc):
        if e["status"] not in ("Active",) or e["join"] > add_days(d, -14):
            return False
        if any(s <= add_days(d, 30) and en >= d for s, en in long_leave[e["id"]]):
            return False
        return st.load_at(e["id"], d) + alloc <= 100

    def meets(e, role, d):
        sk = e["skills"]
        if exp_at(e, d) < role["min_exp"]:
            return False
        if any(n not in sk or sk[n]["prof"] is None or sk[n]["prof"] < mp for n, mp in role["must"]):
            return False
        valid = {c["cert_id"] for c in e["certs"] if cert_valid_on(c, d)}
        return all(c in valid for c in role["mcerts"])

    boosts = []
    open_roles = [(p, r) for p, r, _ in role_rows
                  if (p["status"] == "Pipeline" and r["family"] != "pm") or r["demand_type"] != "Initial"]
    for p, r in open_roles:
        d = r["start"]
        target = max(6, 3 * r["headcount"]) + 2   # margin: injected data-quality issues may knock a few out
        fams = [r["family"]] + FAMILIES[r["family"]]["alt_families"][:1]
        elig = [e for e in emps if available(e, d, r["alloc"]) and meets(e, r, d)]
        if len(elig) >= target:
            continue
        pool = [e for f in fams for e in st.by_family[f] if e not in elig and available(e, d, r["alloc"])
                and exp_at(e, d) >= r["min_exp"]]
        if len(pool) < target - len(elig):   # free people up: schedule realistic roll-offs before the start date
            busy = [e for f in fams for e in st.by_family[f] if e["status"] == "Active" and e not in pool and e not in elig
                    and exp_at(e, d) >= r["min_exp"] and e["join"] <= add_days(d, -14)]
            rng.shuffle(busy)
            for e in busy:
                if len(pool) >= target - len(elig):
                    break
                for a in st.assignments:
                    if a["employee_id"] == e["id"] and a["start"] < d <= a["end"] and a["start"] <= TODAY:
                        a["end"] = max(add_days(d, -rng.randint(2, 12)), add_days(TODAY, 1))
                        a["release_reason"] = "Planned roll-off"
                        boosts.append(dict(kind="planned_roll_off", employee_id=e["id"], project_role_id=r["id"],
                                           detail=f"assignment on {a['project_id']} ends before {d}"))
                st.rebuild_intervals()
                if available(e, d, r["alloc"]):
                    pool.append(e)
        pool.sort(key=lambda e: -sum(1 for n, mp in r["must"] if n in e["skills"] and (e["skills"][n]["prof"] or 0) >= mp))
        for e in pool[: target - len(elig)]:
            for n, mp in r["must"]:
                cur = e["skills"].get(n)
                if not cur or (cur["prof"] or 0) < mp:
                    e["skills"][n] = dict(prof=min(5, mp + (rng.random() < 0.35)),
                                          years=max((cur or {}).get("years", 0), round(rng.uniform(1, max(1.5, exp_at(e, TODAY) * 0.6)) * 2) / 2),
                                          verified=rng.random() < 0.5, last_used=(cur or {}).get("last_used"),
                                          acquired=(cur or {}).get("acquired") or add_days(TODAY, -rng.randint(60, 700)))
                    boosts.append(dict(kind="skill", employee_id=e["id"], project_role_id=r["id"], detail=f"{n}>={mp}"))
            for cid in r["mcerts"]:
                if not any(c["cert_id"] == cid and cert_valid_on(c, d) for c in e["certs"]):
                    e["certs"].append(make_cert_record(e, CERT[cid], add_days(TODAY, -rng.randint(30, 500))))
                    boosts.append(dict(kind="cert", employee_id=e["id"], project_role_id=r["id"], detail=cid))
    for a in st.assignments:
        a["status"] = "Completed" if a["end"] < TODAY else ("Upcoming" if a["start"] > TODAY else "Active")

    # ad-hoc query coverage: every skill and every live certification has available holders
    soon = add_days(TODAY, 14)
    avail_now = [e for e in emps if available(e, soon, 50)]
    for name, cat, _, since in SKILLS:
        need = 3 if cat == "Domain" else 4
        minp = 2 if cat == "Domain" else 3
        have = [e for e in avail_now if name in e["skills"] and (e["skills"][name]["prof"] or 0) >= minp]
        if len(have) >= need:
            continue
        fams = [f for f, spec in FAMILIES.items()
                if name in spec["common"] + spec["occasional"] or any(name in t[2] for t in spec["tracks"])]
        cands = [e for e in avail_now if e not in have and (e["family"] in fams or not fams)]
        rng.shuffle(cands)
        for e in cands[: need - len(have)]:
            yrs = round(min(skill_years_cap(e, name), rng.uniform(1, 4)) * 2) / 2 or 0.5
            e["skills"][name] = dict(prof=rng.choice([3, 3, 4]), years=yrs, verified=rng.random() < 0.5,
                                     acquired=add_days(TODAY, -yrs * 365.25 - rng.randint(0, 90)))
            boosts.append(dict(kind="skill_coverage", employee_id=e["id"], project_role_id=None, detail=name))
    for c in CERTS:
        if c.get("retired_on"):
            continue
        have = [e for e in avail_now if any(x["cert_id"] == c["cert_id"] and cert_valid_on(x, TODAY) for x in e["certs"])]
        if len(have) >= 2:
            continue
        fams = [f for f, spec in FAMILIES.items() if c["cert_id"] in spec["certs"] or any(c["cert_id"] in t[3] for t in spec["tracks"])]
        cands = [e for e in avail_now if e["family"] in fams and e["level"] >= c.get("min_level", 1) and e not in have]
        rng.shuffle(cands)
        for e in cands[: 2 - len(have)]:
            e["certs"].append(make_cert_record(e, c, rand_date(max(D(c["available_from"]), add_days(TODAY, -600)), add_days(TODAY, -20))))
            boosts.append(dict(kind="cert_coverage", employee_id=e["id"], project_role_id=None, detail=c["cert_id"]))

    # ---- appraisal ratings (FY 2025-26: Apr 2025 - Mar 2026)
    fy_s, fy_e = date(2025, 4, 1), date(2026, 3, 31)
    per_emp = defaultdict(list)
    for a in st.assignments:
        if a.get("performance_rating") and fy_s <= a["end"] <= add_days(fy_e, 120):
            per_emp[a["employee_id"]].append(a["performance_rating"])
    for e in emps:
        r = per_emp.get(e["id"])
        if e["join"] > fy_e or e["status"] == "Exited" and e["exit"] < fy_e:
            e["appraisal"] = None
        elif r:
            e["appraisal"] = int(clip(round(sum(r) / len(r) + rng.gauss(0, 0.35)), 1, 5))
        else:
            e["appraisal"] = int(clip(round(3.2 + 0.5 * e["ability"] + rng.gauss(0, 0.5)), 1, 5))

    # ---- reporting managers
    for e in emps:
        seniors = [x for x in st.by_family[e["family"]] if x["level"] > e["level"] and x["status"] != "Exited"]
        if e["level"] >= 5 or not seniors:
            seniors = [x for x in emps if x["family"] == "pm" and x["level"] == 6 and x["status"] != "Exited" and x is not e]
        same_loc = [x for x in seniors if x["location"] == e["location"] and x["level"] <= e["level"] + 2]
        e["manager"] = rng.choice(same_loc or seniors)["id"] if seniors else None

    # ---- data-quality issues injected on purpose (ground truth for the trust layer)
    dq = []
    skill_rows = [(e, n) for e in emps if e["status"] != "Exited" for n in e["skills"]]
    for e, n in rng.sample(skill_rows, int(len(skill_rows) * 0.025)):
        e["skills"][n]["prof"] = None
        dq.append(dict(issue_type="missing_proficiency", employee_id=e["id"], item=n,
                       description="Proficiency left blank in the skills matrix"))
    evidenced = {(a["employee_id"], n) for a in st.assignments for n in [m for m, _ in a["role"]["must"]] + a["role"]["nice"]}
    unevid = [(e, n) for e, n in skill_rows if (e["id"], n) not in evidenced and e["skills"][n]["prof"]
              and SKILL_META[n]["category"] != "Domain"]
    for e, n in rng.sample(unevid, int(len(skill_rows) * 0.03)):
        e["skills"][n].update(prof=rng.choice([4, 5]), years=max(e["skills"][n]["years"], rng.choice([3, 4, 5, 6])), verified=False)
        e["skills"][n].pop("last_used", None)
        dq.append(dict(issue_type="claimed_not_evidenced", employee_id=e["id"], item=n,
                       description="Self-declared expert level with no project evidence and no manager verification"))
    for e, n in rng.sample(skill_rows, int(len(skill_rows) * 0.006)):
        tot = exp_at(e, e["exit"] or TODAY)
        e["skills"][n]["years"] = round(tot + rng.uniform(1.5, 4)) * 1.0
        dq.append(dict(issue_type="skill_years_exceed_experience", employee_id=e["id"], item=n,
                       description="Years of skill use is greater than total career experience"))
    live = [e for e in emps if e["status"] != "Exited"]
    for e in rng.sample(live, int(len(live) * 0.02)):
        tenure = years_between(e["join"], TODAY)
        e["total_exp_override"] = round(max(0.1, tenure - rng.uniform(0.6, 2.0)), 1)
        dq.append(dict(issue_type="experience_inconsistent", employee_id=e["id"], item="total_experience_years",
                       description="Recorded total experience is lower than tenure at Nexora"))
    for e in rng.sample([x for x in live if any(c["expiry"] for c in x["certs"])], 4):
        c = rng.choice([c for c in e["certs"] if c["expiry"]])
        if c["expiry"]:
            c["issue"], c["expiry"] = c["expiry"], c["issue"]
            dq.append(dict(issue_type="cert_dates_swapped", employee_id=e["id"], item=c["cert_id"],
                           description="Issue date is after expiry date (data-entry error)"))
    for e in rng.sample([x for x in live if st.load_at(x["id"], TODAY) >= 100 and x["family"] != "pm"], 4):
        e["email"] = None
        dq.append(dict(issue_type="missing_email", employee_id=e["id"], item="email",
                       description="No email on record - notification cannot be sent"))

    write_outputs(emps, by_id, projects, role_rows, st, leaves, clients, skills_ref, aliases, certs_ref,
                  cert_skills, latent_rows, dq, boosts, client_dm, open_roles, available, meets)


# ----------------------------------------------------------------------------- outputs
POLICIES = [
    ("POL01", "Maximum allocation", "MAX_ALLOCATION_PCT", "100", True,
     "Total allocation across projects cannot exceed 100% without Delivery Head approval."),
    ("POL02", "Allocation warning threshold", "WARN_ALLOCATION_PCT", "80", False,
     "Show a workload warning when allocation after assignment would exceed 80%."),
    ("POL03", "Maximum concurrent projects", "MAX_CONCURRENT_PROJECTS", "3", True,
     "An engineer may work on at most 3 projects at the same time (project managers: 4)."),
    ("POL04", "Project manager concurrency", "PM_MAX_CONCURRENT_PROJECTS", "4", True,
     "A project manager may manage at most 4 projects concurrently."),
    ("POL05", "Mandatory certification validity", "MANDATORY_CERT_MUST_BE_VALID", "true", True,
     "Certifications marked mandatory for a role must be valid (not expired) on the role start date."),
    ("POL06", "Notice period", "BLOCK_IF_EXIT_BEFORE_ROLE_END", "true", True,
     "Employees serving notice cannot be assigned to roles that start after their last working day."),
    ("POL07", "Long leave", "BLOCK_IF_LONG_LEAVE_WITHIN_DAYS", "30", True,
     "Employees with approved leave longer than 10 days starting within 30 days of the role start are not assignable."),
    ("POL08", "Experience tolerance", "MIN_EXPERIENCE_TOLERANCE_YEARS", "1", False,
     "Candidates up to 1 year below the minimum experience may be shown as 'stretch' candidates with a warning."),
    ("POL09", "Bench priority", "BENCH_PRIORITY_DAYS", "30", False,
     "Employees unallocated for more than 30 days should be prioritised when equally suitable."),
    ("POL10", "Induction period", "NEW_JOINER_INDUCTION_DAYS", "14", True,
     "New joiners cannot be assigned during their first 14 days (induction and training)."),
    ("POL11", "Default minimum proficiency", "DEFAULT_MIN_PROFICIENCY", "3", False,
     "When a requirement does not specify a level, proficiency 3 (Intermediate) is expected."),
    ("POL12", "Protected attributes", "SENSITIVE_ATTRIBUTES_EXCLUDED", "gender,date_of_birth,age_band", True,
     "Protected attributes must never be used for ranking; they are used only for fairness audits."),
    ("POL13", "Human approval", "HUMAN_APPROVAL_REQUIRED", "true", True,
     "Every assignment requires explicit approval by the requesting manager with a recorded reason."),
]

SKILL_LEVEL_NAMES = {1: "Beginner", 2: "Elementary", 3: "Intermediate", 4: "Advanced", 5: "Expert"}
INT_COLUMNS = ("rating", "proficiency", "validity_months", "available_since_year", "relationship_since",
               "career_break_months", "headcount", "allocation_pct", "planned_team_size")


def write_outputs(emps, by_id, projects, role_rows, st, leaves, clients, skills_ref, aliases, certs_ref,
                  cert_skills, latent_rows, dq, boosts, client_dm, open_roles, available, meets):
    def save(name, rows, cols=None, folder=OUT):
        df = pd.DataFrame(rows, columns=cols)
        for col in df.columns:
            if df[col].dtype.kind == "f" and df[col].dropna().apply(float.is_integer).all() and col.endswith(INT_COLUMNS):
                df[col] = df[col].astype("Int64")   # e.g. ratings with blanks: write 3, not 3.0
            if df[col].map(lambda v: isinstance(v, str)).any():
                df[col] = df[col].map(lambda v: v.replace("–", "-") if isinstance(v, str) else v)
        df.to_csv(folder / f"{name}.csv", index=False)
        return df

    save("clients", [dict(c, account_delivery_manager_id=client_dm[c["client_id"]]) for c in clients])
    save("skills", skills_ref)
    save("skill_aliases", aliases)
    save("certifications", certs_ref)
    save("certification_skills", cert_skills)
    save("policies", [dict(policy_id=a, policy_name=b, rule_key=c, rule_value=d, is_hard_constraint=e, description=f)
                      for a, b, c, d, e, f in POLICIES])

    emp_rows, sens_rows, skill_rows, cert_rows = [], [], [], []
    for e in emps:
        ref = TODAY if e["status"] != "Exited" else e["exit"]
        total = e.get("total_exp_override", round(exp_at(e, min(ref, TODAY)), 1))
        emp_rows.append(dict(
            employee_id=e["id"], first_name=e["first"], last_name=e["last"], full_name=e["full_name"], email=e["email"],
            designation=e["designation"], job_level=f"L{e['level']}", practice=FAMILIES[e["family"]]["practice"],
            role_family=e["family"], primary_skill=e["primary_skill"], location=e["location"], work_mode=e["work_mode"],
            date_of_joining=iso(e["join"]), prior_experience_years=e["prior_exp"], total_experience_years=total,
            highest_qualification=e["degree"], career_break_months=e["career_break"],
            reporting_manager_id=e["manager"], employment_status=e["status"],
            exit_date=iso(e["exit"]) if e["status"] in ("Exited", "Serving Notice") else None,
            last_appraisal_rating=e["appraisal"], appraisal_cycle="FY2025-26" if e["appraisal"] else None))
        age = years_between(e["dob"], TODAY)
        sens_rows.append(dict(employee_id=e["id"], gender=e["gender"], date_of_birth=iso(e["dob"]),
                              age_band="20-29" if age < 30 else "30-39" if age < 40 else "40-49" if age < 50 else "50+"))
        for n, s in e["skills"].items():
            lu = s.get("last_used")
            if not lu and s["prof"] and e["status"] != "Exited" and rng.random() < 0.7:
                lu = add_days(TODAY, -rng.randint(60, 1100))
            skill_rows.append(dict(employee_id=e["id"], skill_id=SKILL_ID[n], proficiency=s["prof"],
                                   proficiency_label=SKILL_LEVEL_NAMES.get(s["prof"]), years_used=s["years"],
                                   last_used_date=iso(lu), is_manager_verified=s["verified"],
                                   acquired_on=iso(s["acquired"])))
        for c in e["certs"]:
            cert_rows.append(dict(employee_id=e["id"], cert_id=c["cert_id"], credential_id=c["credential"],
                                  issue_date=iso(c["issue"]), last_renewed_on=iso(c["renewed"]),
                                  expiry_date=iso(c["expiry"]), verification_status=c["verification"]))
    cert_rows.sort(key=lambda r: (r["employee_id"], r["issue_date"]))
    for i, r in enumerate(cert_rows, start=1):
        r["employee_cert_id"] = f"EC{i:05d}"
    emp_df = save("employees", emp_rows)
    save("employee_sensitive_attributes", sens_rows)
    save("employee_skills", skill_rows)
    save("employee_certifications", cert_rows,
         ["employee_cert_id", "employee_id", "cert_id", "credential_id", "issue_date", "last_renewed_on", "expiry_date",
          "verification_status"])

    # projects & demands
    filled = Counter(a["project_role_id"] for a in st.assignments if a["status"] in ("Active", "Upcoming"))
    ever = Counter(a["project_role_id"] for a in st.assignments)
    proj_rows, role_out, rskill_out, rcert_out = [], [], [], []
    for p in projects:
        ratings = [a["performance_rating"] for a in st.assignments if a["project_id"] == p["id"] and a.get("performance_rating")]
        outcome, csat = None, None
        if p["status"] == "Completed":
            avg = sum(ratings) / len(ratings) if ratings else 3.3
            outcome = ("Closed early by client" if rng.random() < 0.03 else
                       "Delivered on schedule" if avg + rng.gauss(0, 0.35) >= 3.45 else
                       "Delivered with minor delay" if avg + rng.gauss(0, 0.35) >= 3.0 else "Delivered with significant delay")
            csat = round(clip(avg + rng.gauss(0.6, 0.45), 2.0, 5.0), 1)
        stack = []
        for r in p["roles"]:
            stack += [n for n, _ in r["must"]]
        proj_rows.append(dict(
            project_id=p["id"], project_code=p["code"], project_name=p["name"], client_id=p["client_id"],
            industry=p["industry"], project_type=p["ptype"], engagement_model=p["engagement"],
            description=p["description"], tech_stack=", ".join(dict.fromkeys(stack)), start_date=iso(p["start"]),
            end_date=iso(p["end"]), status=p["status"], priority=p["priority"], delivery_location=p["location"],
            project_manager_id=p["pm_id"], delivery_manager_id=p["dm_id"],
            planned_team_size=sum(r["headcount"] for r in p["roles"]), created_on=iso(p["created_on"]),
            outcome=outcome, client_csat=csat))
        for r in p["roles"]:
            if r["demand_type"] != "Initial" or p["status"] == "Pipeline":
                dstatus = "Filled" if filled[r["id"]] >= r["headcount"] else ("Partially Filled" if filled[r["id"]] else "Open")
            elif p["status"] == "Completed" or r["end"] < TODAY:
                dstatus = "Closed"
            else:
                dstatus = "Filled" if ever[r["id"]] else "Cancelled"
            role_out.append(dict(project_role_id=r["id"], project_id=p["id"], role_title=r["title"], role_family=r["family"],
                                 headcount=r["headcount"], min_experience_years=r["min_exp"], allocation_pct=r["alloc"],
                                 start_date=iso(r["start"]), end_date=iso(r["end"]), demand_type=r["demand_type"],
                                 demand_status=dstatus,
                                 created_on=iso(add_days(min(r["start"], TODAY), -rng.randint(5, 30)) if r["demand_type"] != "Initial" else p["created_on"])))
            rskill_out += [dict(project_role_id=r["id"], skill_id=SKILL_ID[n], min_proficiency=mp, importance="Mandatory")
                           for n, mp in r["must"]]
            rskill_out += [dict(project_role_id=r["id"], skill_id=SKILL_ID[n], min_proficiency=None, importance="Preferred")
                           for n in dict.fromkeys(r["nice"]) if n not in [m for m, _ in r["must"]]]
            rcert_out += [dict(project_role_id=r["id"], cert_id=c, importance="Mandatory") for c in dict.fromkeys(r["mcerts"])]
            rcert_out += [dict(project_role_id=r["id"], cert_id=c, importance="Preferred")
                          for c in dict.fromkeys(r["certs"]) if c not in r["mcerts"]]
    save("projects", proj_rows)
    save("project_roles", role_out)
    save("project_role_skills", rskill_out)
    save("project_role_certifications", rcert_out)

    # assignments & feedback
    st.assignments.sort(key=lambda a: (a["start"], a["project_id"], a["employee_id"]))
    idx_to_id = {}
    asg_rows, fb_rows = [], []
    for i, a in enumerate(st.assignments, start=1):
        a["id"] = f"ASG{i:05d}"
        asg_rows.append(dict(
            assignment_id=a["id"], employee_id=a["employee_id"], project_id=a["project_id"],
            project_role_id=a["project_role_id"], role_title=a["role_title"], allocation_pct=a["allocation_pct"],
            start_date=iso(a["start"]), end_date=iso(a["end"]), status=a["status"], billable=a["billable"],
            assigned_by=a["assigned_by"], assigned_on=iso(a["assigned_on"]), release_reason=a["release_reason"],
            performance_rating=a.get("performance_rating")))
        if a.get("performance_rating") and rng.random() < 0.7:
            top = a["role"]["must"][0][0] if a["role"]["must"] else "delivery"
            txt = rng.choice(FEEDBACK[a["performance_rating"]]).format(skill=top, project=a["proj"]["name"])
            if a.get("overloaded") and rng.random() < 0.5:
                txt += OVERLOAD_NOTE
            fb_rows.append(dict(assignment_id=a["id"], given_by=a["assigned_by"],
                                feedback_date=iso(add_days(a["end"], rng.randint(3, 30))),
                                rating=a["performance_rating"], comments=txt))
        if "_latent" in a:
            latent_rows[a["_latent"]]["assignment_id"] = a["id"]
    save("assignments", asg_rows)
    for i, r in enumerate(fb_rows, start=1):
        r["feedback_id"] = f"FB{i:05d}"
    save("assignment_feedback", fb_rows, ["feedback_id", "assignment_id", "given_by", "feedback_date", "rating", "comments"])

    leaves.sort(key=lambda l: (l["start"], l["employee_id"]))
    save("employee_leaves", [dict(leave_id=f"LV{i:04d}", employee_id=l["employee_id"], leave_type=l["leave_type"],
                                  start_date=iso(l["start"]), end_date=iso(l["end"]), status=l["status"])
                             for i, l in enumerate(leaves, start=1)])

    # application users: managers who raise demands, plus HR and audit roles
    users = []
    for e in emps:
        if e["family"] == "pm" and e["level"] >= 4 and e["status"] == "Active":
            users.append(dict(employee_id=e["id"], full_name=e["full_name"], email=e["email"], app_role="manager"))
    users += [dict(employee_id=None, full_name="Rekha Menon", email=f"rekha.menon@{EMAIL_DOMAIN}", app_role="hr_admin"),
              dict(employee_id=None, full_name="Imran Qureshi", email=f"imran.qureshi@{EMAIL_DOMAIN}", app_role="hr_admin"),
              dict(employee_id=None, full_name="Lakshmi Narayanan", email=f"lakshmi.narayanan@{EMAIL_DOMAIN}", app_role="auditor")]
    for i, u in enumerate(users, start=1):
        u["user_id"] = f"USR{i:03d}"
        u["is_active"] = True
    save("app_users", users, ["user_id", "employee_id", "full_name", "email", "app_role", "is_active"])

    # ---- ground truth (evaluation only; never loaded into the app's model path)
    save("assignment_latent_scores", latent_rows, folder=GT)
    save("data_quality_issues", dq, folder=GT)
    save("demo_coverage_adjustments", boosts, folder=GT)

    # ---- generation report
    act = emp_df[emp_df.employment_status != "Exited"]
    load = {e["id"]: st.load_at(e["id"], TODAY) for e in emps}
    nproj = {e["id"]: st.n_projects_at(e["id"], TODAY) for e in emps}
    act_ids = list(act.employee_id)
    loads = np.array([load[i] for i in act_ids])
    lines = ["# Data generation report", "", f"Snapshot date: {TODAY}  |  seed: {SEED}  |  company: {COMPANY}", "",
             "## Volumes", ""]
    for f in sorted(OUT.glob("*.csv")):
        lines.append(f"- {f.stem}: {sum(1 for _ in open(f, encoding='utf-8')) - 1:,} rows")
    lines += ["", "## Workforce today", "",
              f"- Employees (all time): {len(emps)}; current: {len(act)} "
              f"({(act.employment_status == 'Serving Notice').sum()} serving notice, {(act.employment_status == 'On Long Leave').sum()} on long leave)",
              f"- Bench (0% allocated): {(loads == 0).mean():.1%}",
              f"- Partially allocated (1-99%): {((loads > 0) & (loads < 100)).mean():.1%}",
              f"- Fully allocated (100%): {(loads == 100).mean():.1%}",
              f"- Over-allocated (>100%): {(loads > 100).mean():.1%}",
              f"- On 2+ concurrent projects: {np.mean([nproj[i] >= 2 for i in act_ids]):.1%}",
              f"- Projects: {Counter(p['status'] for p in projects)}", "",
              "## Demo coverage: eligible candidates per open demand (hard filters only)", "",
              "| Project | Role | Start | Headcount | Eligible |", "|---|---|---|---|---|"]
    for p, r in open_roles:
        n = sum(1 for e in emps if available(e, r["start"], r["alloc"]) and meets(e, r, r["start"]))
        lines.append(f"| {p['id']} {p['name'][:45]} | {r['title']} | {r['start']} | {r['headcount']} | {n} |")
    lines += ["", f"Coverage adjustments applied: {Counter(b['kind'] for b in boosts)}",
              f"Injected data-quality issues: {Counter(d['issue_type'] for d in dq)}"]
    lines = [ln.replace("–", "-") for ln in lines]
    (GT / "generation_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()
