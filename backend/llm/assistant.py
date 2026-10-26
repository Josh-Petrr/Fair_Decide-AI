"""Q&A about a recommendation. Answers come only from the engine's computed results.
Names are replaced by aliases before anything is sent to Groq and restored afterwards."""
import json
import re

from ..config import GROQ_MODEL_SMART
from . import groq_client

SYSTEM = """You are FairDecide's staffing assistant for a manager. Answer ONLY from the JSON context. Never invent
facts, numbers, skills or people. If the context does not contain the answer, say so. Be concise (max ~120 words),
use plain business language, mention relevant risks/flags, and remember the manager makes the final decision.
Definitions: success_probability = model's estimate that the person performs well (rating >= 4).
Workload is % allocation: workload_today = now; workload_on_role_start = on the role's start date BEFORE this
assignment (lower than today if current projects end first); workload_after_assignment = on the start date if assigned.
top_factors impacts are percentage points of predicted success. Do not show internal IDs."""


def _mentioned(store, question, pool_ids):
    q = question.lower()
    hits = [eid for eid, e in store.emp.items() if e["employment_status"] != "Exited" and e["full_name"].lower() in q]
    if not hits:   # first names only count for people already in this result
        hits = [eid for eid in pool_ids
                if re.search(r"\b" + re.escape(store.emp[eid]["full_name"].split()[0].lower()) + r"\b", q)]
    return hits[:3]


def _card(c):
    return dict(name=c["name"], designation=c["designation"], success_probability=c["success_probability"],
                confidence=c["confidence"], evidence_score=c["evidence_score"],
                top_factors=c["factors"][:4], skills=[f"{s['skill']} {s['level'] or '?'}/5 (needs {s['required']})" for s in c["skills"]],
                experience_years=c["experience_years"], similar_projects=c["similar_projects"][:1],
                workload_today=c["workload_now"], workload_on_role_start=c["workload_on_start"],
                workload_after_assignment=c["workload_after"],
                current_projects=[f"{p['project']} ({p['allocation']}% until {p['ends']})" for p in c["current_projects"]],
                flags=c["flags"])


def answer(rec, role, question):
    result = rec.recommend(role)
    st = rec.store
    pool_ids = [c["employee_id"] for c in result["candidates"]] + [n["employee_id"] for n in result["near_misses"]]
    why = [rec.why_not(role, eid) for eid in _mentioned(st, question, pool_ids)]
    context = dict(role=result["role"], pool=result["pool"], fairness=result["fairness"],
                   candidates=[_card(c) for c in result["candidates"][:5]],
                   near_misses=[dict(name=n["name"], blocker=n["blocker"], success_probability=n["success_probability"])
                                for n in result["near_misses"]],
                   people_asked_about=[dict(name=w["employee"]["name"], eligible=w["eligible"], blockers=w["blockers"],
                                            warnings=w["warnings"], workload_today=w["employee"]["workload_now"],
                                            workload_on_role_start=w["employee"]["workload_on_start"]) for w in why])

    text = groq_answer(context, question)
    return (text, "groq") if text else (rule_answer(context, question), "rules")


def groq_answer(context, question):
    if not groq_client.available():
        return None
    names = [c["name"] for c in context["candidates"]] + [n["name"] for n in context["near_misses"]] + \
            [p["name"] for p in context["people_asked_about"]]
    alias = {n: f"Person {chr(65 + i)}" for i, n in enumerate(dict.fromkeys(names))}
    payload, q = json.dumps(context, default=str), question
    for n, a in alias.items():
        payload, q = payload.replace(n, a), re.sub(re.escape(n), a, q, flags=re.I)
        first = n.split()[0]
        q = re.sub(r"\b" + re.escape(first) + r"\b", a, q, flags=re.I)
    out = groq_client.chat(GROQ_MODEL_SMART, SYSTEM, f"Context:\n{payload}\n\nQuestion: {q}", max_tokens=400)
    if not out:
        return None
    for n, a in alias.items():
        out = out.replace(a, n)
    return out.strip()


def rule_answer(ctx, question):
    q = question.lower()
    if ctx["people_asked_about"]:
        parts = []
        for p in ctx["people_asked_about"]:
            if p["eligible"]:
                rank = next((i + 1 for i, c in enumerate(ctx["candidates"]) if c["name"] == p["name"]), None)
                parts.append(f"{p['name']} is eligible" + (f" and ranked #{rank}." if rank else
                             ", but other candidates scored higher on predicted success."))
            else:
                parts.append(f"{p['name']} is not shortlisted: " + "; ".join(p["blockers"]) + ".")
        return " ".join(parts)
    cands = ctx["candidates"]
    if not cands:
        return "No one currently meets every mandatory requirement. Check the near misses or relax a requirement in what-if."
    if "compare" in q and len(cands) >= 2:
        a, b = cands[0], cands[1]
        return (f"{a['name']} ({a['success_probability']:.0%}, {a['confidence']} confidence) vs {b['name']} "
                f"({b['success_probability']:.0%}, {b['confidence']}). {a['name']}'s strongest factor is "
                f"{a['top_factors'][0]['factor'].lower()}; {b['name']}'s is {b['top_factors'][0]['factor'].lower()}. "
                f"Workload after assignment: {a['workload_after']}% vs {b['workload_after']}%."
                + (f" Note for {a['name']}: {a['flags'][0]}." if a["flags"] else ""))
    if any(w in q for w in ("risk", "flag", "concern", "issue")):
        flagged = [f"{c['name']}: {'; '.join(c['flags'])}" for c in cands if c["flags"]]
        return "Flags raised: " + (" | ".join(flagged) if flagged else "none for the shortlisted candidates.")
    if "fair" in q or "bias" in q or "gender" in q:
        f = ctx["fairness"]
        return (f"Fairness check: women are {f['women_in_shortlist']:.0%} of the shortlist vs {f['women_in_eligible_pool']:.0%} "
                f"of the eligible pool (status: {f['status']}). {f['note']}")
    top = cands[0]
    return (f"{top['name']} is the strongest match ({top['success_probability']:.0%} predicted success, {top['confidence']} "
            f"confidence), driven mainly by {top['top_factors'][0]['factor'].lower()}. "
            f"{len(cands)} eligible candidates are shortlisted out of {ctx['pool']['eligible']} who pass every hard rule."
            + (f" Watch: {top['flags'][0]}." if top["flags"] else ""))
