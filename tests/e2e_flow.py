"""End-to-end check of the business flow against a running API (+ Mailpit).

Run:  .venv\\Scripts\\python -m tests.e2e_flow          (API on :8000, Mailpit on :8025)
NOTE: it creates real assignments - run  python -m backend.admin reset  afterwards.
"""
import os
import re
import threading
import time

import httpx

API = os.getenv("FD_API", "http://127.0.0.1:8000") + "/api"
MAIL = os.getenv("FD_MAIL", "http://127.0.0.1:8025") + "/api/v1"
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
    first = mgr["full_name"].split()[0]
    results.append(ok(c.post("/auth/login", json={"user_id": mgr["user_id"], "password": "wrong"}).status_code == 401
                      and c.post("/auth/login", json={"user_id": mgr["user_id"]}).status_code == 422, "wrong or missing password refused"))
    tok = c.post("/auth/login", json={"user_id": mgr["user_id"], "password": first}).json()["token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    results.append(ok(c.get("/auth/me").json()["user_id"] == mgr["user_id"], f"login as manager {mgr['full_name']}"))
    results.append(ok(c.get("/dashboard").status_code == 200, "dashboard loads"))

    def as_user(user):
        cl = httpx.Client(base_url=API, timeout=60)
        t = cl.post("/auth/login", json={"user_id": user["user_id"], "password": user["full_name"].split()[0]}).json()["token"]
        cl.headers["Authorization"] = f"Bearer {t}"
        return cl
    by_id = {u["user_id"]: u for u in users}

    demands = c.get("/demands").json()
    d = next(x for x in demands if x["mine"] and x["headcount"] > x["filled"])
    role = d["project_role_id"]
    t = time.time()
    rec = c.get(f"/demands/{role}/recommendations").json()
    results.append(ok(len(rec["candidates"]) >= 2, f"recommendations for '{d['role_title']}' on {d['project_name']} "
                                                    f"({len(rec['candidates'])} candidates, {time.time() - t:.2f}s)"))
    first, second = rec["candidates"][0], rec["candidates"][1]
    results.append(ok(bool(first["explanation"]) and first["factors"], "each candidate has an explanation and SHAP factors"))
    results.append(ok(rec["access"]["can_allocate"] and first["approvers"], f"head sees approvers: {[a['name'] for a in first['approvers']]}"))

    wn = c.get(f"/demands/{role}/why-not/{rec['near_misses'][0]['employee_id']}").json() if rec["near_misses"] else None
    results.append(ok(wn is None or not wn["eligible"], "why-not explains a near miss" if wn else "no near misses to explain"))

    wi = c.post(f"/demands/{role}/whatif", json={"allocation": 50}).json()
    results.append(ok(wi["pool"]["eligible"] >= rec["pool"]["eligible"], f"what-if at 50% allocation: eligible "
                                                                          f"{rec['pool']['eligible']} -> {wi['pool']['eligible']}"))

    # permissions: only the head allocates, everyone can view
    other = as_user(next(u for u in users if u["app_role"] == "manager" and u["user_id"] != mgr["user_id"]
                         and u["user_id"] not in [a["user_id"] for a in first["approvers"]]))
    view = other.get(f"/demands/{role}/recommendations").json()
    results.append(ok(not view["access"]["can_allocate"] and len(view["candidates"]) == len(rec["candidates"]) and len(other.get("/employees").json()) > 50,
                      "another manager can view people and the demand but not allocate"))
    body = {"role_id": role, "employee_ids": [first["employee_id"]], "reason": "Best skill match, free on start date", "request_id": rec["request_id"]}
    results.append(ok(other.post("/allocations", json=body).status_code == 403, "another manager's allocation request is refused"))
    results.append(ok(other.post("/decisions", json=dict(body, decision="reject")).status_code == 403, "another manager cannot reject on this project"))
    results.append(ok(c.post("/decisions", json=dict(body, decision="approve")).status_code == 403, "assigning directly (skipping approval) is refused"))
    results.append(ok(c.post("/allocations", json=dict(body, reason="x")).status_code == 422, "request without a proper reason is refused"))

    # dashboard shows only my projects; a manager with free people can offer them to another project's head
    me = c.get("/employees/" + mgr_emp).json() if (mgr_emp := c.get("/auth/me").json()["employee_id"]) else None
    head_mgr = as_user(next(u for u in users if u["full_name"] == "Allen D'Souza"))
    team, rest = head_mgr.get("/employees?scope=mine").json(), head_mgr.get("/employees?scope=others").json()
    t_ids, r_ids = {x["employee_id"] for x in team}, {x["employee_id"] for x in rest}
    results.append(ok(team and rest and not t_ids & r_ids and head_mgr.get("/meta").json()["team_size"] >= len(team), f"My team and All employees never overlap (Allen: {len(team)} shown)"))
    results.append(ok(me["employee"]["manager_name"] == "Nandini Banerjee", "employee profile includes the manager's name"))
    results.append(ok(c.get("/meta").json()["team_size"] > 0, "a project manager now has a team"))
    outsider = rest[0]
    found = c.get("/employees", params={"q": outsider["full_name"]}).json()
    results.append(ok(any(x["employee_id"] == outsider["employee_id"] for x in found), "search covers everyone, not just my team"))
    results.append(ok(all(u["project_role_id"] in {x["project_role_id"] for x in demands if x["mine"]} for u in c.get("/dashboard").json()["urgent_demands"]),
                      "dashboard lists only the manager's own demands"))
    results.append(ok(next(i for i, x in enumerate(demands) if not x["mine"]) == sum(x["mine"] for x in demands), "all demands list puts my projects first"))
    dm_user = next(u for u in users if u["full_name"] == "Allen D'Souza")
    dm = as_user(dm_user)
    theirs = [x for x in dm.get("/demands").json() if not x["mine"]]
    results.append(ok(dm.get(f"/demands/{role}/recommendations").json()["access"]["can_suggest"], "another manager is offered the suggest option"))
    results.append(ok(c.post("/suggestions", json={"role_id": role, "employee_ids": [first["employee_id"]]}).status_code in (403, 409)
                      and dm.post("/suggestions", json={"role_id": role, "employee_ids": ["NXT10001"]}).status_code == 403, "cannot suggest someone outside your free team"))
    from backend.services.approvals import _managers_above, load_org, route
    org = load_org()
    by_name = {v["full_name"]: k for k, v in org.items()}

    def offered_directly(u, x, p):  # u is this person's own manager, so someone is above u on the route
        steps = route(org, by_name[x["head_name"]], p["employee_id"])
        return not any(a["relation"] == "Your manager" and a["user_id"] == u["user_id"] for a in steps) and \
            any(a["user_id"] == u["user_id"] and a["relation"].endswith("'s manager") and not a["relation"].startswith("Above") for a in steps) and \
            any(a["relation"].startswith("Above") for a in steps)

    x = offer = None
    for mid in dict.fromkeys(_managers_above(org, f["employee_id"])[0]["employee_id"] for f in c.get("/employees?load=free").json()):
        dm_user = next(u for u in users if u["user_id"] == org[mid]["user_id"])
        dm = as_user(dm_user)
        x, offer = next(((x, p) for x in dm.get("/demands").json() if not x["mine"] for p in dm.get(f"/demands/{x['project_role_id']}/bench-team").json()
                         if not p["blockers"] and offered_directly(dm_user, x, p)), (None, None))
        if offer:
            break
    results.append(ok(offer, f"{dm_user['full_name']} has a free, eligible person for another project: {offer and offer['name']} -> {x and x['role_title']}"))
    head = as_user(next(u for u in users if u["full_name"] == x["head_name"]))
    r = dm.post("/suggestions", json={"role_id": x["project_role_id"], "employee_ids": [offer["employee_id"]], "note": "Free from Monday"})
    got = head.get("/inbox").json()["suggestions"]
    results.append(ok(r.status_code == 200 and got and got[0]["employee_id"] == offer["employee_id"] and got[0]["suggested_by"] == dm_user["full_name"], f"{x['head_name']} is notified about {offer['name']}"))
    results.append(ok(dm.post(f"/suggestions/{got[0]['suggestion_id']}/dismiss").status_code == 403, "only the head can act on it"))
    results.append(ok(head.post(f"/suggestions/{got[0]['suggestion_id']}/dismiss").json()["status"] == "dismissed" and not head.get("/inbox").json()["suggestions"], "head can dismiss it"))
    dm.post("/suggestions", json={"role_id": x["project_role_id"], "employee_ids": [offer["employee_id"]]})
    got = head.get("/inbox").json()["suggestions"]
    results.append(ok(next(a for a in got[0]["approvers"] if a["user_id"] == dm_user["user_id"])["status"] == "approved", "the head sees the offering manager already ticked"))
    results.append(ok(head.post(f"/suggestions/{got[0]['suggestion_id']}/accept").json()["status"] == "accepted", "accepting raises an allocation request"))
    w = head.get("/inbox").json()["waiting"][0]
    mine_a = next(a for a in w["approvers"] if a["user_id"] == dm_user["user_id"])
    rest = [a for a in w["approvers"] if a["user_id"] != dm_user["user_id"]]
    results.append(ok(w["employee_id"] == offer["employee_id"] and mine_a["status"] == "approved" and not any(i["allocation_id"] == w["allocation_id"] for i in dm.get("/inbox").json()["to_approve"]),
                      "the offer counts as the offering manager's own approval"))
    above = next(a for a in rest if a["relation"].startswith("Above"))
    results.append(ok(w["status"] == "pending" and above["status"] == "pending" and head.post(f"/allocations/{w['allocation_id']}/send", json={}).status_code == 409,
                      f"their manager still has to approve: {above['name']}"))
    for a in rest:
        as_user(by_id[a["user_id"]]).post(f"/allocations/{w['allocation_id']}/respond", json={"approve": True})
    sent = head.post(f"/allocations/{w['allocation_id']}/send", json={}).json()
    results.append(ok(sent["decision"] == "modified" and c.get(f"/audit/{sent['decision_id']}").status_code == 200, "someone outside the shortlist is recorded as a manager's own pick"))

    # checking one named person against my own demand, workload always included
    url = f"/employees/{first['employee_id']}/eligibility"
    e = c.post(url, json={"role_id": role}).json()
    results.append(ok(e["eligible"] and e["success_probability"] and e["workload"]["after"] == e["workload"]["on_start"] + e["role"]["allocation"],
                      f"eligibility: {first['name']} passes; workload {e['workload']['on_start']}% -> {e['workload']['after']}%"))
    near = rec["near_misses"][0]
    e = c.post(f"/employees/{near['employee_id']}/eligibility", json={"role_id": role}).json()
    results.append(ok(not e["eligible"] and e["success_probability"] is None and e["blockers"], f"eligibility explains a failure: {e['blockers']}"))
    busy = c.get("/employees?load=over").json()[0]["employee_id"]
    e = c.post(f"/employees/{busy}/eligibility", json={"role_id": role, "mandatory_skills": [], "mandatory_certs": [], "min_experience": 0, "allocation": 10}).json()
    results.append(ok(not e["eligible"] and any("Would be at" in b for b in e["blockers"]) and e["workload"]["after"] > 100,
                      f"relaxing every requirement never skips workload: {e['blockers'][-2:]}"))
    e = c.post(url, json={"role_id": role}).json()
    results.append(ok(e["approvers"] and e["positions_left"] >= 1 and e["request_status"] is None, f"eligibility shows approvers {[x['name'] for x in e['approvers']]}"))
    relaxed = c.post(url, json={"role_id": role, "allocation": 10}).json()
    real = c.get(f"/demands/{role}/recommendations").json()["role"]
    results.append(ok(relaxed["role"]["allocation"] == 10 and real["allocation"] == d["allocation_pct"], "changed requirements are not saved"))
    results.append(ok(other.post(url, json={"role_id": role}).status_code == 403, "only the project head can check against their demand"))
    results.append(ok(c.post("/employees/NXT10001/eligibility", json={"role_id": role}).status_code == 409, "someone who has left cannot be checked"))

    # rejected request: nothing is assigned or emailed
    before = httpx.get(f"{MAIL}/messages").json()["total"]
    r = c.post("/allocations", json=dict(body, employee_ids=[second["employee_id"]])).json()["requests"][0]
    nay = as_user(by_id[r["approvers"][0]["user_id"]])
    results.append(ok(nay.post(f"/allocations/{r['allocation_id']}/respond", json={"approve": False}).status_code == 422, "rejecting needs a reason"))
    res = nay.post(f"/allocations/{r['allocation_id']}/respond", json={"approve": False, "comment": "Needed on my release until January"})
    results.append(ok(res.json()["status"] == "rejected" and c.get("/inbox").json()["rejected"][0]["approvers"][0]["comment"].startswith("Needed"),
                      "a rejection reaches the head with its reason"))
    results.append(ok(c.post(f"/allocations/{r['allocation_id']}/send", json={}).status_code == 409, "a rejected request cannot be sent"))

    # approved request: email and database only change at send
    r = c.post("/allocations", json=body).json()["requests"][0]
    aid, names = r["allocation_id"], [a["name"] for a in r["approvers"]]
    results.append(ok(c.post("/allocations", json=body).status_code == 409, "the same request cannot be made twice"))
    results.append(ok(other.post(f"/allocations/{aid}/respond", json={"approve": True}).status_code == 403, "someone who is not an approver cannot approve"))
    results.append(ok(c.post(f"/allocations/{aid}/send", json={}).status_code == 409 and c.get("/inbox").json()["waiting"][0]["allocation_id"] == aid,
                      f"cannot send early; head sees it waiting on {names}"))
    for i, a in enumerate(r["approvers"]):
        ap = as_user(by_id[a["user_id"]])
        results.append(ok(any(x["allocation_id"] == aid for x in ap.get("/inbox").json()["to_approve"]), f"{a['name']} ({a['relation']}) sees it in notifications"))
        st = ap.post(f"/allocations/{aid}/respond", json={"approve": True}).json()["status"]
        results.append(ok(st == ("approved" if i == len(r["approvers"]) - 1 else "pending"), f"{a['name']} approves -> {st}"))
    prof = c.get(f"/employees/{first['employee_id']}").json()
    time.sleep(1)
    results.append(ok(httpx.get(f"{MAIL}/messages").json()["total"] == before and c.get("/inbox").json()["ready"][0]["allocation_id"] == aid
                      and not any(a["project_role_id"] == role for a in prof["assignments"] if "project_role_id" in a),
                      "fully approved: ready to send, still no email"))
    r = c.post(f"/allocations/{aid}/send", json={})
    res = r.json()
    results.append(ok(r.status_code == 200 and res["decision"] == "approved", f"send assigns {first['name']} -> {res}"))
    results.append(ok(c.post(f"/allocations/{aid}/send", json={}).status_code == 409, "it cannot be sent twice"))

    prof = c.get(f"/employees/{first['employee_id']}").json()
    results.append(ok(any(a["assignment_id"] in res["assignments"] for a in prof["assignments"]),
                      "database now shows the new assignment on the employee"))
    results.append(ok(prof["employee"]["manager_name"] == mgr["full_name"] and first["employee_id"] in {e["employee_id"] for e in c.get("/employees?scope=mine").json()},
                      f"{first['name']} now reports to {mgr['full_name']} and appears in My team"))
    dem_after = {x["project_role_id"]: x for x in c.get("/demands").json()}.get(role)
    results.append(ok(dem_after is None or dem_after["filled"] == d["filled"] + 1, "demand fill count updated"))

    for _ in range(20):
        if httpx.get(f"{MAIL}/messages").json()["total"] > before:
            break
        time.sleep(0.5)
    msgs = httpx.get(f"{MAIL}/messages").json()
    results.append(ok(msgs["total"] == before + 1 and first["email"] in str(msgs["messages"][0]["To"]),
                      f"email delivered to Mailpit: '{msgs['messages'][0]['Subject']}'"))
    notes = c.get("/notifications").json()
    results.append(ok(notes[0]["status"] == "sent", "notification status = sent"))

    r = c.post("/decisions", json={"role_id": role, "decision": "reject", "request_id": rec["request_id"],
                                   "reason": "Client asked to hold the second position"})
    results.append(ok(r.status_code == 200 and r.json()["decision"] == "rejected", "reject decision recorded"))
    audit = c.get("/audit").json()
    results.append(ok(audit[0]["decision"] == "rejected" and audit[1]["decision"] == "approved", "audit trail has both decisions"))
    detail = c.get(f"/audit/{audit[1]['decision_id']}").json()
    results.append(ok(len(detail["candidates"]) == len(rec["candidates"]), "audit keeps the full recommended list + explanations"))
    time.sleep(1)
    results.append(ok({"allocation", "decision", "notification"} <= set(seen), f"live events received: {sorted(set(seen))}"))

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

    # ---------------------------------------------------------------- request comment from an eligibility check
    me_demands = [x for x in c.get("/demands").json() if x["mine"]]
    hand = None
    for dd in me_demands:
        top = {x["employee_id"] for x in c.get(f"/demands/{dd['project_role_id']}/recommendations").json()["candidates"]}
        for e in c.get("/employees?available=true").json():
            if e["employee_id"] not in top and c.post(f"/employees/{e['employee_id']}/eligibility", json={"role_id": dd["project_role_id"]}).json()["eligible"]:
                hand = (dd, e)
                break
        if hand:
            break
    dd, e = hand
    r = c.post("/allocations", json={"role_id": dd["project_role_id"], "employee_ids": [e["employee_id"]], "reason": "Worked together on the last release",
                                      "source": "eligibility"}).json()["requests"][0]
    ap = as_user(by_id[r["approvers"][0]["user_id"]])
    seen_by = next(x for x in ap.get("/inbox").json()["to_approve"] if x["allocation_id"] == r["allocation_id"])
    results.append(ok(seen_by["source"] == "eligibility" and seen_by["reason"] == "Worked together on the last release",
                      "approver sees a hand-picked request with the manager's comment"))
    results.append(ok(c.post("/allocations", json={"role_id": dd["project_role_id"], "employee_ids": [e["employee_id"]], "reason": "x",
                                                    "source": "eligibility"}).status_code in (409, 422), "a request needs a real comment"))
    results.append(ok(c.post("/allocations", json={"role_id": dd["project_role_id"], "employee_ids": [e["employee_id"]], "reason": "Looks good to me",
                                                    "source": "suggestion"}).status_code == 422, "a request cannot pretend to be another manager's offer"))
    c.post(f"/allocations/{r['allocation_id']}/cancel")

    # ---------------------------------------------------------------- admin
    adm = as_user(next(u for u in users if u["app_role"] == "admin"))
    results.append(ok(c.get("/admin/users").status_code == 403 and adm.post("/allocations", json={"role_id": role, "employee_ids": [], "reason": "admin try"}).status_code == 403,
                      "only the admin opens Admin, and the admin cannot allocate"))
    meta = c.get("/meta").json()
    sk = {x["skill_name"]: x["skill_id"] for x in meta["skills"]}
    nandini = c.get("/employees", params={"q": "Nandini Banerjee"}).json()[0]["employee_id"]
    new = adm.post("/admin/employees", json={"first_name": "Kavin", "last_name": "Testmanager", "designation": "Project Manager", "job_level": "L4",
                                             "role_family": "pm", "location": meta["locations"][0], "date_of_joining": "2026-09-01", "prior_experience_years": 8,
                                             "reporting_manager_id": nandini, "skills": [{"skill_id": sk["Agile / Scrum"], "level": 4}]})
    kid = new.json().get("employee_id")
    prof = c.get(f"/employees/{kid}").json()
    results.append(ok(new.status_code == 200 and prof["employee"]["manager_name"] == "Nandini Banerjee" and prof["skills"][0]["proficiency"] == 4,
                      f"admin adds an employee with skills and a manager: {new.json()}"))
    results.append(ok(adm.post("/admin/employees", json={**{"first_name": "No", "last_name": "Skills", "designation": "Dev", "job_level": "L2", "role_family": "python",
                                                            "location": meta["locations"][0], "date_of_joining": "2026-09-01", "reporting_manager_id": nandini}, "skills": []}).status_code == 422,
                      "an employee needs at least one skill"))
    hemant_u = next(u for u in users if u["full_name"] == "Hemant Tripathi")
    hemant = as_user(hemant_u)
    hd = [x for x in hemant.get("/demands").json() if x["mine"]]
    hrec = hemant.get(f"/demands/{hd[0]['project_role_id']}/recommendations").json()
    hreq = hemant.post("/allocations", json={"role_id": hd[0]["project_role_id"], "employee_ids": [hrec["candidates"][0]["employee_id"]],
                                             "reason": "Best fit before I leave", "request_id": hrec["request_id"]}).json()["requests"][0]
    pv = adm.get("/admin/handover/preview", params={"from_user": hemant_u["user_id"], "to_employee": kid}).json()
    results.append(ok(len(pv["projects"]) >= 1 and len(pv["requests"]) == 1 and not pv["successor_is_manager"],
                      f"handover preview: {len(pv['projects'])} projects, {len(pv['reports'])} reports, {len(pv['requests'])} open request"))
    done = adm.post("/admin/handover", json={"from_user": hemant_u["user_id"], "to_employee": kid}).json()
    kavin = as_user({"user_id": done["successor_user"], "full_name": "Kavin Testmanager"})
    results.append(ok(len([x for x in kavin.get("/demands").json() if x["mine"]]) == len(hd)
                      and any(w["allocation_id"] == hreq["allocation_id"] for w in kavin.get("/inbox").json()["waiting"]),
                      "the successor now heads the projects and owns the open request"))
    results.append(ok(hemant.get("/auth/me").status_code == 401 and c.get(f"/employees/{kid}").json()["employee"]["manager_name"] == "Nandini Banerjee",
                      "the leaving manager's login is closed; the successor takes their place under Nandini"))
    gone = next(u for u in adm.get("/admin/users").json() if u["user_id"] == hemant_u["user_id"])
    results.append(ok(not gone["is_active"] and gone["end_date"] and gone["projects"] == 0 and gone["reports"] == 0, "the leaver keeps their history but holds nothing"))
    results.append(ok(adm.post("/admin/managers", json={"employee_id": kid}).status_code == 409, "the same person cannot get two logins"))
    hired = adm.post("/admin/employees", json={"first_name": "Ishaan", "last_name": "Newhire", "designation": "Project Manager", "job_level": "L4",
                                               "role_family": "pm", "location": meta["locations"][0], "date_of_joining": "2026-10-20", "prior_experience_years": 9,
                                               "reporting_manager_id": nandini, "make_manager": True, "skills": [{"skill_id": sk["Agile / Scrum"], "level": 4}]}).json()
    logins = {u["full_name"]: u for u in c.get("/auth/users").json()}
    results.append(ok(hired["user_id"] and "Ishaan Newhire" in logins and next(u for u in adm.get("/admin/users").json() if u["user_id"] == hired["user_id"])["start_date"] == "2026-10-20",
                      "hiring a new manager creates the employee and their login, managing from the joining date"))
    pick = next(e for e in c.get("/employees", params={"q": "Python"}).json() if e["employment_status"] == "Active" and e["job_level"] in ("L3", "L4")
                and e["full_name"] not in logins)
    pr = adm.post("/admin/managers", json={"employee_id": pick["employee_id"], "designation": "Project Manager", "job_level": "L4"})
    after = c.get(f"/employees/{pick['employee_id']}").json()["employee"]
    results.append(ok(pr.status_code == 200 and after["designation"] == "Project Manager" and after["job_level"] == "L4"
                      and pick["full_name"] in {u["full_name"] for u in c.get("/auth/users").json()},
                      f"promoting {pick['full_name']} gives a login and the new title"))

    print(f"\n{sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
