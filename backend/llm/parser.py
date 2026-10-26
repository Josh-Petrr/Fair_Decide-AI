"""Plain-English staffing request -> structured requirements the manager confirms.

Groq does the reading when a key is configured; a rule-based parser is the fallback. Either way every skill and
certification is resolved against the real catalogue, so the output can never contain an invented skill.
"""
import re
from datetime import date, timedelta

import numpy as np

from ..config import GROQ_MODEL_SMART
from ..db import fetch_all
from ..engine.embeddings import embed
from . import groq_client

FAMILY_WORDS = [  # first match wins
    ("pm", r"project manager|scrum master|delivery manager"), ("ba", r"business analyst|\bba\b|product owner"),
    ("ux", r"\bux\b|\bui/ux\b|designer"), ("security", r"security|pen ?test|vapt|\biam\b"),
    ("salesforce", r"salesforce|\bsfdc\b"), ("data_sci", r"data scientist|machine learning|\bml\b|gen ?ai|\bnlp\b|computer vision"),
    ("data_eng", r"data engineer|etl|databricks|snowflake|\bbi developer|power bi"),
    ("devops", r"devops|\bsre\b|cloud engineer|platform engineer|kubernetes"), ("qa", r"\bqa\b|tester|test automation|quality"),
    ("mobile", r"android|\bios\b|flutter|react native|mobile"), ("fullstack", r"full ?stack|mern|node"),
    ("frontend", r"front ?end|react|angular|\bui developer"), ("dotnet", r"\.net|c#|dotnet"),
    ("python", r"python|django|fastapi"), ("java", r"java|spring"),
]
TITLES = {"java": "Java Developer", "dotnet": ".NET Developer", "python": "Python Developer", "frontend": "Frontend Developer",
          "fullstack": "Full Stack Developer", "mobile": "Mobile Developer", "data_eng": "Data Engineer",
          "data_sci": "Data Scientist", "devops": "DevOps Engineer", "qa": "QA Engineer", "salesforce": "Salesforce Developer",
          "ba": "Business Analyst", "pm": "Project Manager", "ux": "UX Designer", "security": "Security Engineer"}
NUMBERS = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
AMBIGUOUS = {"go", "rest", "ts", "cv", "bq", "rn", "xd", "ado", "r", "express", "compose", "glue", "elastic", "fabric", "flows"}
CLAUSE_SPLIT = re.compile(r"[.;\n]|,(?=[^,]*\b(?:nice to have|good to have|preferred|a plus|bonus)\b)|\bbut\b")
CERT_WORDS = {"istqb": "ISTQB-CTFL", "pmp": "PMP", "csm": "CSM", "scrum master certification": "CSM", "cka": "CKA",
              "ckad": "CKAD", "aws solutions architect": "AWS-SAA", "aws certified": "AWS-SAA", "saa": "AWS-SAA",
              "terraform associate": "HC-TFA", "ceh": "CEH", "cissp": "CISSP", "security+": "COMPTIA-SEC",
              "snowpro": "SNOW-CORE", "safe agilist": "SAFE-SA", "itil": "ITIL4-F", "pl-300": "PL-300"}
PREFERRED_CUE = re.compile(r"\b(nice to have|good to have|preferred|preferably|bonus|plus|ideally|optional)\b", re.I)


class Catalogue:
    """Skills and certifications with every way people refer to them."""
    def __init__(self):
        self.skills = fetch_all("SELECT skill_id, skill_name, category FROM skills")
        self.domain = {s["skill_id"] for s in self.skills if s["category"] == "Domain"}
        self.terms = {}
        for s in self.skills:
            self.terms[s["skill_name"].lower()] = s["skill_id"]
        for a in fetch_all("SELECT skill_id, alias FROM skill_aliases"):
            self.terms.setdefault(a["alias"].lower(), a["skill_id"])
        self.name = {s["skill_id"]: s["skill_name"] for s in self.skills}
        self.vecs = embed([s["skill_name"] for s in self.skills])
        self.certs = fetch_all("SELECT cert_id, cert_name, exam_code FROM certifications WHERE retired_on IS NULL")

    def resolve_skill(self, text):
        t = text.lower().strip()
        if t in self.terms:
            return self.terms[t]
        sims = self.vecs @ embed([text])[0]
        i = int(np.argmax(sims))
        return self.skills[i]["skill_id"] if sims[i] >= 0.62 else None

    def resolve_cert(self, text):
        t = text.lower()
        for c in self.certs:
            code = (c["exam_code"] or "").lower()
            if c["cert_id"].lower() == t or (len(code) > 2 and code in t) or c["cert_name"].lower() in t or t in c["cert_name"].lower():
                return c["cert_id"]
        return None

    def find_in_text(self, text):
        """Skill ids mentioned in free text. A clause containing a cue ('nice to have', 'a plus', 'preferred')
        makes its skills preferred; domain knowledge is always preferred; everything else is mandatory."""
        must, nice = [], []
        for clause in CLAUSE_SPLIT.split(text.lower()):
            preferred = bool(PREFERRED_CUE.search(clause))
            for term, sid in sorted(self.terms.items(), key=lambda kv: -len(kv[0])):
                if len(term) < 2 or term in AMBIGUOUS:
                    continue
                for m in re.finditer(r"(?<![\w.#+])" + re.escape(term) + r"(?![\w#+])", clause):
                    if sid not in must and sid not in nice:
                        (nice if preferred or sid in self.domain else must).append(sid)
                    clause = clause[:m.start()] + " " * len(term) + clause[m.end():]   # don't double-count aliases
        return must, nice

    def certs_in_text(self, text):
        """[(cert_id, mandatory)] - preferred if its clause carries a 'preferred' cue."""
        out = {}
        for clause in CLAUSE_SPLIT.split(text.lower()):
            preferred = bool(PREFERRED_CUE.search(clause))
            found = [cid for word, cid in CERT_WORDS.items() if re.search(r"\b" + re.escape(word) + r"\b", clause)]
            for c in self.certs:
                code = (c["exam_code"] or "").lower()
                if (len(code) > 3 and re.search(r"\b" + re.escape(code) + r"\b", clause)) or \
                        re.search(r"\b" + re.escape(c["cert_id"].lower()) + r"\b", clause):
                    found.append(c["cert_id"])
            for cid in found:
                out.setdefault(cid, not preferred)
        return list(out.items())


_cat = None


def catalogue():
    global _cat
    if _cat is None:
        _cat = Catalogue()
    return _cat


MONTH_RE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATE_RE = re.compile(r"(?:(?:from|starting|start|starts|in|by|on|begin\w*)\s+(?:(\d{1,2})\s+)?" + MONTH_RE + r"(?:\s+(\d{4}))?)"
                     r"|(?:(\d{1,2})\s+" + MONTH_RE + r"(?:\s+(\d{4}))?)|(?:" + MONTH_RE + r"\s+(\d{4}))", re.I)


def _parse_date(text, today):
    """Dates need context ('from March', '15 Jan', 'Feb 2027') so words like 'may' are not misread."""
    m = DATE_RE.search(text)
    if not m:
        return None
    g = m.groups()
    day, mon, year = next(((d, mo, y) for d, mo, y in ((g[0], g[1], g[2]), (g[3], g[4], g[5]), (None, g[6], g[7])) if mo))
    month = MONTHS[mon.lower()[:3]]
    d = date(int(year) if year else today.year, month, int(day) if day else 1)
    return d if d > today or year else date(d.year + 1, month, d.day)


def rule_based(text, today):
    low = text.lower()
    cat = catalogue()
    family = next((f for f, pat in FAMILY_WORDS if re.search(pat, low)), "java")
    hc = re.search(r"\b(\d+|one|two|three|four|five|six|an?)\s+(?:senior |junior |lead |experienced )?[a-z.#+/ -]{0,30}?"
                   r"(developers?|engineers?|testers?|analysts?|designers?|architects?|scientists?|leads?|managers?|resources?)", low)
    headcount = (int(hc.group(1)) if hc.group(1).isdigit() else NUMBERS.get(hc.group(1), 1)) if hc else 1
    exp = re.search(r"(\d+)\s*\+?\s*(?:years|yrs)", low)
    min_exp = float(exp.group(1)) if exp else (7 if "lead" in low or "architect" in low else 5 if "senior" in low else 1 if "junior" in low else 2)
    alloc = re.search(r"(\d{2,3})\s*%", low)
    start = _parse_date(text, today) or today + timedelta(days=30)
    dur = re.search(r"(\d+)\s*months?", low)
    end = start + timedelta(days=30.44 * (int(dur.group(1)) if dur else 9))
    must, nice = cat.find_in_text(text)
    certs = cat.certs_in_text(text)
    seniority = "Senior " if min_exp >= 5 and family not in ("pm", "ba") else ""
    return dict(title=seniority + TITLES[family], family=family, headcount=headcount, min_experience=min_exp,
                allocation=min(100, int(alloc.group(1))) if alloc else 100, start_date=str(start), end_date=str(end),
                mandatory_skills=[dict(skill_id=s, min_level=4 if min_exp >= 7 else 3) for s in must],
                preferred_skills=nice, mandatory_certs=[c for c, m in certs if m], preferred_certs=[c for c, m in certs if not m])


SYSTEM = """You turn a manager's staffing request into JSON. Use ONLY information in the request; never invent skills.
Return: {"title": str, "family": one of [java, dotnet, python, frontend, fullstack, mobile, data_eng, data_sci, devops,
qa, salesforce, ba, pm, ux, security], "headcount": int, "min_experience": number, "allocation": int 10-100,
"start_date": "YYYY-MM-DD" or null, "duration_months": int or null,
"mandatory_skills": [{"name": str, "min_level": 1-5}], "preferred_skills": [str], "certifications": [{"name": str, "mandatory": bool}]}
Proficiency: 3 = intermediate (default), 4 = senior/strong, 5 = expert. Skills described as nice-to-have/preferred/plus go in
preferred_skills. Today is {today}."""


def parse(text, today):
    """Returns (requirements, source) where source is 'groq' or 'rules'."""
    base = rule_based(text, today)
    out = groq_client.chat(GROQ_MODEL_SMART, SYSTEM.replace("{today}", str(today)), text, json_mode=True)
    if not out:
        return base, "rules"
    cat = catalogue()
    must, unknown = [], []
    for s in out.get("mandatory_skills") or []:
        sid = cat.resolve_skill(str(s.get("name", "")))
        if sid and sid not in [m["skill_id"] for m in must]:
            must.append(dict(skill_id=sid, min_level=int(min(5, max(1, s.get("min_level") or 3)))))
        elif not sid:
            unknown.append(s.get("name"))
    nice = [sid for sid in (cat.resolve_skill(str(n)) for n in out.get("preferred_skills") or []) if sid and sid not in [m["skill_id"] for m in must]]
    certs = [(cat.resolve_cert(str(c.get("name", ""))), bool(c.get("mandatory"))) for c in out.get("certifications") or []]
    start = out.get("start_date") or base["start_date"]
    try:
        sd = date.fromisoformat(start)
    except ValueError:
        sd = date.fromisoformat(base["start_date"])
    months = out.get("duration_months")
    family = out.get("family") if out.get("family") in TITLES else base["family"]
    return dict(title=out.get("title") or base["title"], family=family,
                headcount=int(out.get("headcount") or base["headcount"]),
                min_experience=float(out.get("min_experience") if out.get("min_experience") is not None else base["min_experience"]),
                allocation=int(min(100, max(10, out.get("allocation") or base["allocation"]))),
                start_date=str(sd), end_date=str(sd + timedelta(days=30.44 * months)) if months else base["end_date"],
                mandatory_skills=must or base["mandatory_skills"], preferred_skills=list(dict.fromkeys(nice)),
                mandatory_certs=[c for c, m in certs if c and m], preferred_certs=[c for c, m in certs if c and not m],
                unrecognised_skills=[u for u in unknown if u]), "groq"
