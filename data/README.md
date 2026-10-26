# FairDecide AI – Synthetic Workforce Dataset

Synthetic but realistic data for **Nexora Technologies Pvt. Ltd.**, a fictional mid-size Indian IT services company
(about 800 current employees, 6 delivery centres, 29 client accounts). The snapshot date is **2026-10-26** and history starts in mid-2018.
All people, companies and email addresses are fictional. Emails use the reserved `.example` domain, so they can never reach a real inbox.
Certifications, their vendors and their validity rules are real.

## Regenerate and load

```powershell
docker compose up -d                          # PostgreSQL 17 + pgvector
.venv\Scripts\python -m datagen.generate      # writes data/*.csv  (seed 17, ~5 s)
.venv\Scripts\python -m datagen.diagnostics   # optional sanity checks
.venv\Scripts\python -m db.load_data          # rebuilds schema (db/schema.sql) and loads all CSVs
```

## Tables

| File | Rows | What it holds |
|---|---|---|
| `employees` | 1,450 | Everyone employed since 2018 (≈817 current). Level L1–L6, practice, primary skill, location, experience, status (Active / Serving Notice / On Long Leave / Exited), reporting manager, last appraisal |
| `employee_sensitive_attributes` | 1,450 | Gender, date of birth, age band. Stored in a separate `restricted` schema, used **only** for fairness audits |
| `employee_skills` | ~19k | Skill, proficiency 1–5, years used, last used date, whether a manager verified it |
| `employee_certifications` | ~1.3k | Real certifications with credential IDs, issue, renewal and expiry dates (about 30% expired) |
| `employee_leaves` | ~100 | Planned and current leave (earned, maternity, paternity, sabbatical…) that affects availability |
| `clients` | 29 | Client accounts across 11 industries, each with an account delivery manager |
| `projects` | 754 | Completed, active and 30 **Pipeline** (new) projects with realistic scope descriptions and tech stacks |
| `project_roles` | ~4.4k | Staffing demands: role, headcount, minimum experience, allocation %, dates, status. **Open** rows are the demo queries |
| `project_role_skills` / `project_role_certifications` | ~19k / ~2.3k | Mandatory and preferred skills (with minimum proficiency) and certifications per role |
| `assignments` | ~5.6k | Who worked where, allocation %, dates, release reason, performance rating (1–5) for completed work |
| `assignment_feedback` | ~3.2k | Manager feedback comments on completed assignments |
| `skills`, `skill_aliases` | 195 / 470 | Skill taxonomy, with aliases for semantic normalisation (e.g. "reactjs" → React) |
| `certifications`, `certification_skills` | 63 / 99 | Certification catalogue (vendor, exam code, validity, retirement) and the skills each one evidences |
| `policies` | 13 | Business rules: max 100% allocation, max 3 concurrent projects, valid mandatory certifications, notice and leave blocks… |
| `app_users` | 32 | Managers who raise demands and approve assignments, plus HR admin and auditor users |

## Workforce realism (current snapshot)

- About 15% on bench, 77% fully allocated, about 6.5% over-allocated, and 13% on two or more concurrent projects.
- Utilisation stays between 74% and 86% in every year of history. Attrition peaks in 2021–22.
- Regional Indian naming matched to each office's local workforce mix. The gender mix varies by practice (for example, UX is 55% women and DevOps 20%).
- Skills grow through project work, so most claimed skills have a project trail. Domain knowledge (payments, FHIR, OSS/BSS…) comes from the projects a person actually worked on.
- Every open demand has at least 4 candidates who pass all hard filters (median about 10). Every skill and every live certification has available holders, so ad-hoc manager queries also return results.

## Ground truth (`data/_ground_truth/`, evaluation only, never loaded into the app)

- `assignment_latent_scores.csv` – the hidden suitability function behind each performance rating: skill match, experience fit, domain familiarity, certification match, overload, plus a **deliberately injected bias** (about −0.30 for women, −0.20 for age 45+, −0.15 for a career break). This lets the fairness module show that it detects historical rating bias.
- `data_quality_issues.csv` – deliberately injected problems the trust layer should flag: missing proficiency, expert claims with no evidence, skill years exceeding career length, inconsistent experience, swapped certification dates, missing email.
- `demo_coverage_adjustments.csv` – every change made so the demo always has candidates: added skills or certifications and planned roll-offs.
- `generation_report.md` – volumes, workforce statistics and the eligible-candidate count for every open demand.
