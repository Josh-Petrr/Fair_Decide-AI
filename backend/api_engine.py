"""Recommendation, what-if, why-not, decision and live-update endpoints."""
import json
from datetime import date
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import events, state
from .api_data import SkillReq
from .auth import current_user, manager
from .config import ARTIFACTS
from .db import conn, fetch_all, fetch_one
from .services import approvals, decisions, notifier

router = APIRouter(prefix="/api")


def _role(role_id):
    if role_id not in state.rec.store.roles:
        raise HTTPException(404, "Demand not found")
    return state.rec.store.role_spec(role_id)


@router.get("/demands/{role_id}/recommendations")
def recommendations(role_id: str, top_n: int = 10, user=Depends(current_user)):
    rec = state.rec
    out = rec.recommend(_role(role_id), top_n=top_n)
    # every recommendation shown to a manager is recorded for the audit trail
    with conn() as c:
        rid = c.execute("""INSERT INTO recommendation_requests (project_role_id, requested_by, parsed_requirements, model_version)
                           VALUES (%s, %s, %s, %s) RETURNING request_id""",
                        (role_id, user["user_id"], json.dumps(out["role"]),
                         f"{rec.meta['variant']} (AUC {rec.meta['test_auc']})")).fetchone()["request_id"]
        for cnd in out["candidates"]:
            c.execute("""INSERT INTO recommendation_candidates (request_id, employee_id, rank, match_score, confidence,
                             evidence_score, explanation, explanation_text, flags) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                      (rid, cnd["employee_id"], cnd["rank"], cnd["success_probability"], cnd["confidence"],
                       cnd["evidence_score"], json.dumps(dict(factors=cnd["factors"], skills=cnd["skills"])),
                       cnd["explanation"], json.dumps(cnd["flags"])))
    return dict(out, request_id=rid, access=approvals.access(user, role_id, out["candidates"]))


class WhatIf(BaseModel):
    start_date: date | None = None
    allocation: int | None = Field(None, ge=10, le=100)
    min_experience: float | None = Field(None, ge=0, le=30)
    mandatory_skills: list[SkillReq] | None = None
    preferred_skills: list[str] | None = None
    mandatory_certs: list[str] | None = None        # names, as shown to the manager


def _changed(role, body):
    """A modified copy of the demand - nothing is saved."""
    if body.start_date:
        shift = body.start_date.toordinal() - role["start"]
        role["start"] += shift
        role["end"] = max(role["end"], role["start"] + 30)
    if body.allocation:
        role["alloc"] = body.allocation
    if body.min_experience is not None:
        role["min_exp"] = body.min_experience
    if body.mandatory_skills is not None:
        role["must"] = [(s.skill_id, s.min_level) for s in body.mandatory_skills]
    if body.preferred_skills is not None:
        role["nice"] = body.preferred_skills
    if body.mandatory_certs is not None:
        role["mcerts"] = [c for c in role["mcerts"] if state.rec.store.cert_name[c] in body.mandatory_certs]
    return role


@router.post("/demands/{role_id}/whatif")
def what_if(role_id: str, body: WhatIf, user=Depends(current_user)):
    return state.rec.recommend(_changed(_role(role_id), body))


class EligibilityIn(WhatIf):
    role_id: str


@router.post("/employees/{employee_id}/eligibility")
def eligibility(employee_id: str, body: EligibilityIn, user=Depends(manager)):
    """Can this person fill one of my demands? Runs the same rules as the shortlist, workload included."""
    rec = state.rec
    if employee_id not in rec.store.emp:
        raise HTTPException(404, "Employee not found")
    if rec.store.emp[employee_id]["employment_status"] == "Exited":
        raise HTTPException(409, "This person has left the company.")
    role = _changed(_role(body.role_id), body)
    with conn() as c:
        decisions.require_head(c, user, body.role_id)
    out = rec.eligibility(role, employee_id)
    taken = approvals.access(user, body.role_id, [])["open_requests"]
    return dict(out, approvers=approvals.route(approvals.load_org(), user["employee_id"], employee_id), request_status=taken.get(employee_id),
                positions_left=max(0, role["headcount"] - out["role"]["filled"] - len(taken)))


@router.get("/demands/{role_id}/why-not/{employee_id}")
def why_not(role_id: str, employee_id: str, user=Depends(current_user)):
    if employee_id not in state.rec.store.emp:
        raise HTTPException(404, "Employee not found")
    return state.rec.why_not(_role(role_id), employee_id)


class EmailPreview(BaseModel):
    role_id: str
    employee_ids: list[str]


@router.post("/email-preview")
def email_preview(body: EmailPreview, user=Depends(manager)):
    rows = fetch_all("""SELECT e.employee_id, e.first_name, e.email, r.role_title, p.project_name, c.client_name,
                               p.delivery_location, GREATEST(r.start_date, fd_as_of()) AS start_date, r.end_date, r.allocation_pct
                        FROM employees e, project_roles r JOIN projects p USING (project_id) JOIN clients c USING (client_id)
                        WHERE e.employee_id = ANY(%s) AND r.project_role_id = %s""", (body.employee_ids, body.role_id))
    out = []
    for r in rows:
        subject, text = notifier.compose(dict(r, manager_name=user["full_name"]))
        out.append(dict(employee_id=r["employee_id"], recipient=r["email"], subject=subject, body=text))
    return out


class DecisionIn(BaseModel):
    role_id: str
    decision: str                       # approve | reject
    employee_ids: list[str] = []
    reason: str
    request_id: int | None = None
    notes: str | None = None
    emails: dict[str, dict] | None = None


@router.post("/decisions")
def decide(body: DecisionIn, user=Depends(manager)):
    if body.decision == "approve":                  # assigning always goes through /allocations
        raise HTTPException(403, "Assignments need approval: use a request, then send it once approved.")
    return decisions.decide(state.rec, user, body.role_id, body.decision, [], body.reason, body.request_id, body.notes)


class AllocationIn(BaseModel):
    role_id: str
    employee_ids: list[str]
    reason: str
    request_id: int | None = None
    notes: str | None = None
    source: Literal["shortlist", "eligibility"] = "shortlist"     # offers arrive through /suggestions


class ResponseIn(BaseModel):
    approve: bool
    comment: str | None = None


class SendIn(BaseModel):
    emails: dict[str, dict] | None = None


@router.post("/allocations")
def request_allocation(body: AllocationIn, user=Depends(manager)):
    return approvals.request(state.rec, user, body.role_id, body.employee_ids, body.reason, body.request_id, body.notes, source=body.source)


@router.post("/allocations/{allocation_id}/respond")
def respond_allocation(allocation_id: int, body: ResponseIn, user=Depends(manager)):
    return approvals.respond(user, allocation_id, body.approve, body.comment)


@router.post("/allocations/{allocation_id}/send")
def send_allocation(allocation_id: int, body: SendIn, background: BackgroundTasks, user=Depends(manager)):
    result = approvals.send(state.rec, user, allocation_id, body.emails)
    background.add_task(notifier.send_pending, result["notifications"])
    return result


@router.post("/allocations/{allocation_id}/cancel")
def cancel_allocation(allocation_id: int, user=Depends(manager)):
    return approvals.cancel(user, allocation_id)


class SuggestIn(BaseModel):
    role_id: str
    employee_ids: list[str]
    note: str | None = Field(None, max_length=300)


@router.get("/demands/{role_id}/bench-team")
def bench_team(role_id: str, user=Depends(manager)):
    _role(role_id)
    return approvals.bench_team(state.rec, user, role_id)


@router.post("/suggestions")
def suggest(body: SuggestIn, user=Depends(manager)):
    return approvals.suggest(state.rec, user, body.role_id, body.employee_ids, body.note)


@router.post("/suggestions/{suggestion_id}/accept")
def accept_suggestion(suggestion_id: int, user=Depends(manager)):
    return approvals.close_suggestion(state.rec, user, suggestion_id, True)


@router.post("/suggestions/{suggestion_id}/dismiss")
def dismiss_suggestion(suggestion_id: int, user=Depends(manager)):
    return approvals.close_suggestion(state.rec, user, suggestion_id, False)


@router.get("/inbox")
def inbox(user=Depends(current_user)):
    return approvals.inbox(user)


@router.get("/notifications")
def notifications(user=Depends(current_user)):
    return fetch_all("""SELECT n.notification_id, n.recipient, n.subject, n.status, n.error, n.created_at, n.sent_at,
                               e.full_name FROM notifications n JOIN employees e USING (employee_id)
                        ORDER BY n.created_at DESC LIMIT 20""")


@router.get("/model")
def model_card(user=Depends(current_user)):
    rec = state.rec
    files = {k: (ARTIFACTS / f"{k}.md").read_text(encoding="utf-8") if (ARTIFACTS / f"{k}.md").exists() else ""
             for k in ("evaluation_report", "bias_audit_report", "preprocessing_report")}
    return dict(meta=rec.meta, **files)


@router.get("/stream")
async def stream():
    return StreamingResponse(events.stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class ParseIn(BaseModel):
    text: str = Field(min_length=10, max_length=2000)


@router.post("/assistant/parse")
def assistant_parse(body: ParseIn, user=Depends(current_user)):
    from .llm import parser
    reqs, source = parser.parse(body.text, fetch_one("SELECT fd_as_of() AS d")["d"])
    names = state.rec.store.skill_name
    reqs["mandatory_skills"] = [dict(s, skill=names[s["skill_id"]]) for s in reqs["mandatory_skills"]]
    reqs["preferred_skill_names"] = [names[s] for s in reqs["preferred_skills"]]
    return dict(requirements=reqs, source=source)


class ChatIn(BaseModel):
    role_id: str
    question: str = Field(min_length=3, max_length=500)


@router.post("/assistant/chat")
def assistant_chat(body: ChatIn, user=Depends(current_user)):
    from .llm import assistant
    text, source = assistant.answer(state.rec, _role(body.role_id), body.question)
    return dict(answer=text, source=source)


@router.post("/admin/reload")
def reload_engine(request: Request):
    """Called by `python -m backend.admin reset`; only accepted from this machine."""
    if request.client.host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(403, "Local only")
    with state.rec.lock:
        state.rec.store.load_static()
        state.rec.store.refresh()
    events.publish("reset", {})
    return dict(ok=True)


@router.get("/health")
def health():
    return dict(ok=True, as_of=fetch_one("SELECT fd_as_of() AS d")["d"], model=state.rec.meta["variant"] if state.rec else None)
