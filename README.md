# FairDecide AI – Trustworthy Workplace Decision Assistant

A manager describes a project (or opens an existing one). FairDecide recommends employees for each role based on
skills, experience, certifications, similar past projects and workload. It explains every recommendation, flags data
and workload risks, and checks the shortlist for fairness. The manager approves (human-in-the-loop), and one click then
updates the database and emails the employee.

**Team 17 · MSDS · Josh Peter & Shreya Sharma.** Everything is open source and free: the LLM runs on Groq's free tier, and
the system works fully without it.

## Run the demo

```powershell
powershell -ExecutionPolicy Bypass -File start.ps1
```
This starts PostgreSQL and Mailpit (Docker), resets the demo data, launches the API (:8000) and the web app (:5173), and
opens the app and the demo inbox (http://localhost:8025, where "sent" emails arrive; nothing leaves the machine).

**Signing in:** pick a name, then enter that person's first name as the password (e.g. Afreen Inamdar → `Afreen`, not case-sensitive). This is a demo rule only, not real security.

**Admin:** sign in as *Josh Peter* (password `Josh`) or *Shreya Sharma* (password `Shreya`) to open the **Admin** page: promote an employee or hire a new manager, add employees with their skills, change reporting lines, and hand a leaving manager's projects, team, approvals and requests to a successor in one step. `admin reset` undoes all of it.

**Who can do what:** every manager can view all people and projects, but only a project's head (its project manager) can
allocate people to it. A request goes to the head's manager and, if the employee is in another team, to the employee's
manager and the person above them. Their names are shown before the request is sent, and approvals appear under
*Notifications* on the dashboard. Once everyone approves, the head clicks **Send**: only then is the database updated and
the email sent. The dashboard and *Staffing demands* start on your own projects; *All projects* shows the rest. On someone
else's project, a manager with free people in their team can click **I have someone free** to notify the head, who can turn
it into a normal request. The offer counts as that manager's own approval; everyone else on the route, including their manager, still approves. To test someone you already have in mind, open their profile and click **Check eligibility**: pick one of your roles, adjust the requirements if you like, and see the result and their workload. Nothing is saved unless you click **Request allocation**, which starts the same approvals. Employees report to the manager of their project, and *My team* shows everyone below you at every level; search always covers all employees. When a request is sent, the person moves to that project's head if it is their biggest allocation.

To try two people at once, use a normal and a private browser window, since a browser keeps one sign-in.

## First-time setup

```powershell
docker compose up -d
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
cd frontend; npm install; cd ..
.venv\Scripts\python -m backend.admin setup     # generate data -> load DB -> embeddings -> train model (~2 min)
```
LLM settings in `.env` (check with `.venv\Scripts\python -m backend.llm.selftest`):

```
FAIRDECIDE_LLM_RUNTIME=groq                # or "none" to run fully on the rule-based fallback
FAIRDECIDE_LLM_MODEL=qwen/qwen3.8-27b      # any chat model listed for your key in the Groq console
GROQ_API_KEY=gsk_...
FAIRDECIDE_EMBEDDING_MODEL=all-MiniLM-L6-v2 # 384-dim; changing it requires re-running setup
```

## Architecture

| Layer | What | Where |
|---|---|---|
| Web app | React + Vite + TypeScript + Tailwind; live updates via Server-Sent Events | `frontend/` |
| API | FastAPI: auth, projects, demands, recommendations, what-if, why-not, decisions, audit, stream | `backend/api_*.py` |
| Matching engine | Policy hard-filter → point-in-time features → LightGBM → SHAP, confidence, evidence, flags, fairness check | `backend/engine/` |
| Semantic similarity | all-MiniLM-L6-v2 (fastembed/ONNX, local) + pgvector | `backend/engine/embeddings.py` |
| Language assistant | Groq (model set in `.env`, e.g. Qwen) for request parsing and Q&A, names anonymised; rule-based fallback | `backend/llm/` |
| Approvals | Request -> approvers sign off -> head sends; routing follows the reporting line | `backend/services/approvals.py` |
| Decision service | One transaction: assignments + demand status + decision + audit + queued email, under a lock | `backend/services/` |
| ML pipeline | preprocess → bias audit (rating correction) → reweighing → train/compare/calibrate/evaluate | `backend/ml/` |
| Data | Synthetic Indian IT-services company (1,450 people, 754 projects, real certifications) | `datagen/`, `data/` |
| Database | PostgreSQL 17 + pgvector; protected attributes in a separate `restricted` schema | `db/schema.sql` |

## Model results (test period 2025–26)

| Model | AUC | NDCG@10 vs true suitability | Gender equal-opportunity gap |
|---|---|---|---|
| Hand-weighted baseline formula | 0.750 | 0.879 | – |
| LightGBM on raw (biased) ratings | 0.807 | 0.892 | 0.083 |
| **LightGBM, bias-corrected ratings + reweighing (production)** | **0.808** | **0.902** | **0.019** |

Full reports: `backend/ml/artifacts/*.md` (also shown on the app's *AI transparency* page).

## Tests

```powershell
.venv\Scripts\python -m tests.e2e_flow          # API checks of the full business flow
.venv\Scripts\python -m tests.ui_flow shots     # real-browser walkthrough with screenshots
.venv\Scripts\python -m backend.admin reset     # undo test/demo changes afterwards
```
