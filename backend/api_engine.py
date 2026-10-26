"""Recommendation, what-if, why-not, decision and live-update endpoints."""
import json
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import events, state
from .api_data import SkillReq
from .auth import current_user, manager
from .config import ARTIFACTS
from .db import conn, fetch_all, fetch_one
from .services import decisions, notifier

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
    return dict(out, request_id=rid)


class WhatIf(BaseModel):
    start_date: date | None = None
    allocation: int | None = Field(None, ge=10, le=100)
    min_experience: float | None = Field(None, ge=0, le=30)
    mandatory_skills: list[SkillReq] | None = None
    preferred_skills: list[str] | None = None


@router.post("/demands/{role_id}/whatif")
def what_if(role_id: str, body: WhatIf, user=Depends(current_user)):
    """Same engine on a modified copy of the demand - nothing is saved."""
    role = _role(role_id)
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
    return state.rec.recommend(role)


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
def decide(body: DecisionIn, background: BackgroundTasks, user=Depends(manager)):
    result = decisions.decide(state.rec, user, body.role_id, body.decision, body.employee_ids, body.reason,
                              body.request_id, body.notes, body.emails)
    if result.get("notifications"):
        background.add_task(notifier.send_pending, result["notifications"])
    return result


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
