"""End-to-end check of the business flow against a running API (+ Mailpit).

Run:  .venv\\Scripts\\python -m tests.e2e_flow          (API on :8000, Mailpit on :8025)
NOTE: it creates real assignments - run  python -m backend.admin reset  afterwards.
"""
import re
import threading
import time

import httpx

API, MAIL = "http://127.0.0.1:8000/api", "http://127.0.0.1:8025/api/v1"
def ok(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    return bool(cond)


def main():
    c = httpx.Client(base_url=API, timeout=60)
    for _ in range(60):                                   # wait for startup
        try:
            if c.get("/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(1)
    results = []

    # live event stream, listened to in the background like a browser would
    seen = []

    def listen():
        try:
            with httpx.stream("GET", f"{API}/stream", timeout=None) as r:
                for chunk in r.iter_text():
                    seen.extend(re.findall(r"event: (\w+)", chunk))
        except Exception as exc:
            seen.append(f"listener-error:{exc!r}")
    threading.Thread(target=listen, daemon=True).start()
    for _ in range(100):                                  # like a browser: be subscribed before acting
        if "hello" in seen:
            break
        time.sleep(0.1)

    users = c.get("/auth/users").json()
    mgr = next(u for u in users if u["app_role"] == "manager")
    tok = c.post("/auth/login", json={"user_id": mgr["user_id"]}).json()["token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    results.append(ok(c.get("/auth/me").json()["user_id"] == mgr["user_id"], f"login as manager {mgr['full_name']}"))
    results.append(ok(c.get("/dashboard").status_code == 200, "dashboard loads"))

    demands = c.get("/demands").json()
    d = next(x for x in demands if x["headcount"] - x["filled"] >= 2)
    t = time.time()
    rec = c.get(f"/demands/{d['project_role_id']}/recommendations").json()
    results.append(ok(len(rec["candidates"]) >= 2, f"recommendations for '{d['role_title']}' on {d['project_name']} "
                                                    f"({len(rec['candidates'])} candidates, {time.time() - t:.2f}s)"))
    first, second = rec["candidates"][0], rec["candidates"][1]
    results.append(ok(bool(first["explanation"]) and first["factors"], "each candidate has an explanation and SHAP factors"))

    wn = c.get(f"/demands/{d['project_role_id']}/why-not/{rec['near_misses'][0]['employee_id']}").json() if rec["near_misses"] else None
    results.append(ok(wn is None or not wn["eligible"], "why-not explains a near miss" if wn else "no near misses to explain"))

    wi = c.post(f"/demands/{d['project_role_id']}/whatif", json={"allocation": 50}).json()
    results.append(ok(wi["pool"]["eligible"] >= rec["pool"]["eligible"], f"what-if at 50% allocation: eligible "
                                                                          f"{rec['pool']['eligible']} -> {wi['pool']['eligible']}"))

    r = c.post("/decisions", json={"role_id": d["project_role_id"], "decision": "approve", "employee_ids": [first["employee_id"]],
                                   "reason": "x"})
    results.append(ok(r.status_code == 422, "decision without a proper reason is refused"))

    before = httpx.get(f"{MAIL}/messages").json()["total"]
    r = c.post("/decisions", json={"role_id": d["project_role_id"], "decision": "approve", "request_id": rec["request_id"],
                                   "employee_ids": [first["employee_id"]], "reason": "Best skill match, free on start date"})
    res = r.json()
    results.append(ok(r.status_code == 200 and res["decision"] == "approved", f"approve {first['name']} -> {res}"))

    prof = c.get(f"/employees/{first['employee_id']}").json()
    results.append(ok(any(a["assignment_id"] in res["assignments"] for a in prof["assignments"]),
                      "database now shows the new assignment on the employee"))
    dem_after = {x["project_role_id"]: x for x in c.get("/demands").json()}.get(d["project_role_id"])
    results.append(ok(dem_after is None or dem_after["filled"] == d["filled"] + 1, "demand fill count updated"))

    r = c.post("/decisions", json={"role_id": d["project_role_id"], "decision": "approve", "employee_ids": [first["employee_id"]],
                                   "reason": "Trying to book the same person twice"})
    results.append(ok(r.status_code == 409, f"double-booking blocked: {r.json()['detail']}"))

    for _ in range(20):
        if httpx.get(f"{MAIL}/messages").json()["total"] > before:
            break
        time.sleep(0.5)
    msgs = httpx.get(f"{MAIL}/messages").json()
    results.append(ok(msgs["total"] == before + 1 and first["email"] in str(msgs["messages"][0]["To"]),
                      f"email delivered to Mailpit: '{msgs['messages'][0]['Subject']}'"))
    notes = c.get("/notifications").json()
    results.append(ok(notes[0]["status"] == "sent", "notification status = sent"))

    r = c.post("/decisions", json={"role_id": d["project_role_id"], "decision": "reject", "request_id": rec["request_id"],
                                   "reason": "Client asked to hold the second position"})
    results.append(ok(r.status_code == 200 and r.json()["decision"] == "rejected", "reject decision recorded"))
    audit = c.get("/audit").json()
    results.append(ok(audit[0]["decision"] == "rejected" and audit[1]["decision"] == "approved", "audit trail has both decisions"))
    detail = c.get(f"/audit/{audit[1]['decision_id']}").json()
    results.append(ok(len(detail["candidates"]) == len(rec["candidates"]), "audit keeps the full recommended list + explanations"))
    time.sleep(1)
    results.append(ok({"decision", "notification"} <= set(seen), f"live events received: {sorted(set(seen))}"))

    meta = c.get("/meta").json()
    sk = {s["skill_name"]: s["skill_id"] for s in meta["skills"]}
    new = c.post("/projects", json={
        "project_name": "UPI AutoPay Mandate Management Platform", "client_id": "KCB",
        "description": "Build recurring-payment mandate management on UPI AutoPay for retail customers: mandate creation, "
                       "pre-debit notifications, execution and reconciliation with the core banking system.",
        "start_date": "2026-12-01", "end_date": "2027-08-31", "priority": "High",
        "roles": [{"title": "Senior Java Developer", "family": "java", "headcount": 2, "min_experience": 4,
                   "mandatory_skills": [{"skill_id": sk["Java"], "min_level": 3}, {"skill_id": sk["Spring Boot"], "min_level": 3}],
                   "preferred_skills": [sk["Payments (UPI/IMPS/NEFT)"], sk["Apache Kafka"]]}]})
    results.append(ok(new.status_code == 200, f"new project created: {new.json()}"))
    rec2 = c.get(f"/demands/{new.json()['role_ids'][0]}/recommendations").json()
    top = rec2["candidates"][0]
    results.append(ok(len(rec2["candidates"]) >= 3 and top["similar_projects"],
                      f"new project gets candidates; top: {top['name']} - similar past project "
                      f"'{top['similar_projects'][0]['project']}' ({top['similar_projects'][0]['similarity']})"))
    print(f"\n{sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
