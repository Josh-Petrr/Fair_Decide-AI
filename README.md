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
.venv\Scripts\python -m tests.e2e_flow          # 19 API checks of the full business flow
.venv\Scripts\python -m tests.ui_flow shots     # real-browser walkthrough with screenshots
.venv\Scripts\python -m backend.admin reset     # undo test/demo changes afterwards
```
