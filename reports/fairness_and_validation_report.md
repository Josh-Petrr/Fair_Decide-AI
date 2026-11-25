# FairDecide AI: Fairness Stress Testing and Validation Report

**Team 17:** Josh Peter & Shreya Sharma · **Guide:** Dr. Jawahar S
**Data as of:** 26 Oct 2026 (demo company date) · **Model:** LightGBM "Bias-corrected + reweighing" (24 features, 192 trees)
**Reproduce:** `.venv\Scripts\python -m tests.fairness_audit` (read-only, about 2.5 minutes). The raw numbers are in `backend/ml/artifacts/fairness_audit.json`.

---

## 1. Summary

We stress-tested the recommender against the situations where staffing tools are unfair in practice:
- gender and name;
- career breaks for women and men;
- maternity and paternity leave;
- returning after a long absence;
- historical rating bias;
- age;
- people who over-claim their skills;
- new joiners with no history;
- location and work mode;
- hidden proxies.

Each scenario ran on real candidates and real open demands.

**What holds up:**
- **The model never uses gender, age, name, location or career break directly.** Changing any of these for 400 real top candidates moved their score by exactly **0.00 points**.
- **Leave is treated the same whatever the gender.** The same leave gave the same result for a woman and a man in 150 of 150 cases.
- **A finished maternity or paternity leave has no effect** on the score.
- **The rating correction works.**
  - Women with a career break gain **+18 points** on average.
  - Their shortlist appearances rise from **74 to 91**.
  - Against the bias-free truth, the gap in equal opportunity between women and men is **1.9 points**. It would be 9.2 points with raw ratings.
- **On the 155 live open demands, women's shortlist rate is 95% of men's**, which passes the four-fifths rule.

**What the tests exposed** (details in section 4):

| # | Finding | Severity |
|---|---|---|
| 1 | People with **no past ratings** lose **11.3 points** on average, and 35% of them drop out of the top 5 | High |
| 2 | **Claiming a skill one level higher, unverified,** adds **9.1 points** and lifts 37% of people ranked 6 to 10 into the top 5. A manager verifying a skill adds about **0** | High |
| 3 | The **leave rule is blunt.** A 12-day leave in a role's first month blocks a 6-month role, but a 6-month maternity leave starting in week 5 only shows a warning. Women are blocked by leave **1.5×** as often as men | Medium |
| 4 | The **bias-corrected rating reveals gender** through its decimal part, for example 3.22. On its own it predicts gender with an AUC of **0.88**. The model can't use this, but a human reading the card can | Medium |
| 5 | **A career break costs experience.** An 18-month break costs about 1.8 points, and 8 women fail the minimum-experience rule only because of their break. The rule is gender-neutral, but women take breaks 3× as often and twice as long | Medium |
| 6 | **Returners are penalised for missing projects.** A 12-month gap in project history costs 4.3 points, and 15% drop out of the top 5 | Medium |
| 7 | **Age.** More experience can *lower* the score. Against the truth, people aged 40 to 49 who should be in the top 5 are picked **64%** of the time, against **75 to 76%** for younger groups. Age bias in ratings was never corrected because there were no age-45+ cases in the training years | Medium |
| 8 | The career-break correction **over-corrects for the 19 men with breaks**: they are picked 94% of the time when truly top 5, against 75% | Low |
| 9 | Shortlist rates for **remote workers and people in Pune** are below four-fifths of the best group. The direct effect is zero, so this comes through profile differences in small groups | Monitor |

---

## 2. How we tested

| Method | What it does | Why it matters |
|---|---|---|
| **Counterfactual twins** | Copy a real candidate in memory, change **one** thing, and re-score them on the same real open role. The 400 cases are drawn from the top 5 of the 155 open demands; scenarios that reward a change use 400 people ranked 6 to 10 instead | Tests individual fairness: two people who differ in one respect should be treated the same |
| **Live group outcomes** | Run all 155 open demands through the filters and model, then compare filter pass rates and top-10 shortlist rates by group | Tests group fairness on today's data, using the four-fifths rule |
| **Replay against the truth** | Re-run the **817 roles of the 2025–26 test period** and compare with each person's hidden, bias-free suitability from the data generator | Separates real merit from biased history. Measured as "picked when truly top 5" (equal opportunity) |
| **Proxy test** | Train a separate model to guess gender, career break or age from the 24 model features, with each person kept wholly in one fold | If a protected attribute can be guessed, the model *could* discriminate indirectly |

Nothing is written to the database: twins live only in memory and are deleted at the end of the run. The data is synthetic, generated with *known, injected* biases, so we can check whether the system undoes them:
- in ratings: women −0.30, career break −0.15, age 45+ −0.20;
- women take career breaks more often and for longer.

**Population at the test date:** 817 active people. 303 are women, of whom 33 (10.9%) have a career break averaging 16.2 months. 514 are men, of whom 19 (3.7%) have a career break averaging 7.3 months.

---

## 3. Results by scenario

All score changes are in **percentage points of predicted success**. "Top-5 flips" counts people who left the top 5 or, for scenarios that reward a change, entered it.

### 3.1 Gender and name swap

| Twin | Cases | Mean change | Largest change | Top-5 flips |
|---|---|---|---|---|
| Same person, opposite gender and a typical opposite-gender name (for example Priya Iyer ↔ Rahul Verma) | 400 | 0.00 | 0.00 | 0 |

**Pass.** The engine doesn't load gender, date of birth, age band or career break at all; the design check found none of them in its data. Gender is read only by the fairness monitor, after ranking.

### 3.2 Career break: women and men

A break isn't counted as work experience, so a person who took one has fewer years of experience than a colleague who started work at the same time.

| Break length (experience lost) | Cases | Mean change | Worst | Now fail the experience rule | Top-5 flips |
|---|---|---|---|---|---|
| 6 months | 400 | −0.55 | −9.1 | 4 | 10 |
| 12 months | 400 | −1.10 | −16.5 | 5 | 13 |
| 18 months | 400 | −1.83 | −22.4 | 13 | 19 |
| 24 months | 400 | −2.46 | −33.2 | 20 | 27 |

- **The same break costs a woman and a man the same.** For 18 months the averages were −1.31 for women and −2.17 for men; the difference comes from the profiles involved, since gender isn't read.
- **Real people with breaks, compared with the same person if the break had never happened:**
  - **Women:** 126 person-role checks, **−1.22** points on average, worst −17.3.
  - **Men:** 57 checks, **−0.46** points on average, worst −7.6.
  - **8 women** fail the minimum-experience rule only because of their break. No men do.
- **Verdict:** equal treatment, unequal impact. Women take breaks 3× as often and twice as long, so they carry most of the cost.

### 3.3 Maternity and paternity leave

| Scenario | Result |
|---|---|
| 6-month maternity leave that ended a year ago | Score unchanged (0.00) for 400 of 400 |
| 15-day paternity leave that ended earlier | Score unchanged (0.00) for 400 of 400 |
| 182-day maternity leave starting 1 week into the role | **Blocked** for 400 of 400 |
| 15-day paternity leave starting 1 week into the role | **Blocked** for 400 of 400 |
| 12-day earned leave starting 1 week into the role | **Blocked** for 400 of 400 |
| 10-day paternity leave starting 1 week into the role | Not blocked: only leaves of 12 days or more count |
| 182-day maternity leave starting **5 weeks** into the role | **Not blocked.** Score unchanged; a "Planned leave" warning appears for 100 of 100 |
| 15-day paternity leave starting 5 weeks into the role | Not blocked |
| Identical leave dates for a woman and a man | Identical outcome for 150 of 150 |

**Live data:**
- **Women are excluded for leave in a role's first 30 days 1.5× as often:** 23.4 times per 1,000 eligibility checks, against 15.5 for men.
- **Leaves blocking someone today:** earned leave (8 women, 14 men), maternity (7), paternity (3), medical (4 men), sabbatical (3 men) and marriage (1 woman).
- **Verdict:** the rule is gender-neutral and past leave carries no penalty, which is the most important property. But the rule is **all-or-nothing and depends only on timing**: a short leave early on blocks entirely, while a long leave a month later passes with only a warning.

### 3.4 Returning after a long absence

This scenario covers a person who was on the payroll but did no projects for 12 months, for example extended maternity leave or a long illness.

| Twin | Cases | Mean change | Worst | Top-5 flips |
|---|---|---|---|---|
| Projects from a 12-month window removed | 400 | **−4.34** | −40.7 | **61 (15%)** |

The loss comes from features that count projects and domain experience: total projects, domain projects, and similarity to past projects. The time away reads as less experience. In this sample women lost more on average (−6.2 against −3.2) because more of their recent work fell in that window.

### 3.5 Historical rating bias

| Group | Person-role checks | Mean change from correction | Top-10 appearances: raw → corrected |
|---|---|---|---|
| Women with a career break | 126 | **+18.0** | 74 → **91** |
| Women without a break | 641 | +3.0 | 461 → 458 |
| Men with a career break | 57 | +7.9 | 47 → 51 |
| Men without a break | 997 | 0.0 | 759 → 741 |

**Rating bias audit on the training years:**

| Group | Unexplained gap after controlling for skills and experience | 95% confidence interval |
|---|---|---|
| Women | −0.218 | −0.28 to −0.15 |
| Career break | −0.316 | −0.44 to −0.19 |
| Age 45+ | **Not estimated:** there were 0 assignments at age 45+ in 2018–2023 (10 in 2024–26) | |

### 3.6 Age and seniority

| Twin | Cases | Mean change | Range | Top-5 flips |
|---|---|---|---|---|
| +10 years of experience | 400 | −1.63 | −12.6 to +16.7 | 18 |
| +20 years of experience | 400 | −1.54 | −12.0 to +15.9 | 13 |

The model has no "more is never worse" constraint on experience, level or experience gap, so it learned a mild over-qualification penalty. Experience is also the strongest age proxy: it predicts "40+" with an AUC of 0.98. Against the bias-free truth:

| Age band (today) | Picked when truly top 5 |
|---|---|
| Under 30 | 0.747 |
| 30–39 | 0.760 |
| 40–49 | **0.636** |

### 3.7 Over-claiming skills

| Twin | Cases | Mean change | Range | Top-5 flips |
|---|---|---|---|---|
| Each mandatory skill claimed 1 level higher, unverified (people ranked 1–5) | 400 | +5.07 | −3.3 to +24.2 | 0 (already in the top 5) |
| Same, for people ranked **6–10** | 400 | **+9.09** | −2.5 to +31.7 | **147 enter the top 5 (37%)** |
| Manager verifies all their skills (ranked 1–5) | 400 | −0.09 | −6.2 to +5.5 | 7 |
| Manager verifies all their skills (ranked 6–10) | 400 | +0.34 | −6.6 to +7.9 | 9 |

- **What the system already does:** the card warns "claimed at 4/5 but not verified or used on a project".
- **What it doesn't do:** the score itself rewards a self-rating far more than verification.
- **Why this matters in practice:** studies of self-assessment generally find women rate themselves lower than men with the same ability. Our synthetic data doesn't include that gap, so the effect here is the same for both groups.

### 3.8 New joiners and people with no rating history

| Twin | Cases | Mean change | Worst | Top-5 flips |
|---|---|---|---|---|
| All past ratings removed | 400 | **−11.29** | −39.4 | **139 (35%)** |

The model sends a missing rating down the "low performer" branch, so having no history is treated almost like having a bad one. This mainly hits new joiners and anyone whose past projects weren't rated.

### 3.9 Location and work mode

| Twin | Cases | Mean change |
|---|---|---|
| Moved to another city | 400 | 0.00 |

Live shortlist rate relative to the best group:

| Group | Ratio |
|---|---|
| Remote | 0.72 (40 of 69 shortlisted) |
| Pune | 0.72 |
| Chennai | 0.79 |
| Bengaluru | 0.83 |
| Gurugram | 0.88 |
| Hyderabad | 0.89 |
| Kochi | 1.00 |

The direct effect is zero, so these gaps come from differences in skills and history between these groups, and the groups are small. They need watching, not a model change.

### 3.10 Hidden proxies

Can the model's 24 features reveal a protected attribute? We tested with each person kept in a single fold.

| Attribute | AUC from all 24 features | Without `past_rating` |
|---|---|---|
| Gender (woman) | **0.856** | **0.525** (chance) |
| Career break | 0.719 | |
| Age 40+ | 0.976 (through years of experience, as expected) | |

**Root cause:**
- The bias correction adds a fixed amount per group, so corrected ratings end in .22 for women, .53 for women with a break, and whole numbers or halves for men.
- `past_rating` alone predicts gender with an AUC of 0.881. Raw ratings: 0.563. Corrected rating rounded to 1 decimal: 0.75.

**Why the model can't use it:**
- `past_rating` has a "higher is better" constraint, so the model can't treat .22 differently from .20.
- The gender-swap test confirms no direct effect.

**The real risk** is a human recognising the pattern on the candidate card, which shows the corrected rating.

### 3.11 Live outcomes on the 155 open demands

| Group | Pass the filters (per check) | Shortlist rate once eligible | Four-fifths ratio (shortlist) |
|---|---|---|---|
| Women | 1.63% | 71.6% | **0.95 ✔** |
| Men | 1.32% | 75.1% | 1.00 |
| Career break | 2.27% | 77.6% | 1.00 ✔ |
| No break | 1.38% | 73.2% | 0.94 |
| Under 30 | 0.99% | 63.9% | 0.77 (mostly experience rules, which are job-related) |
| 30–39 | 2.45% | 82.5% | 1.00 |
| 40–49 | 1.97% | 80.0% | 0.97 |

**The live four-fifths monitor:**
- **On the 155 open demands:** 134 "ok", **15 "review: women under-represented"** and 6 with too few candidates.
- **Unit check:** an all-men shortlist triggers "review", and a balanced one shows "ok".

### 3.12 Replay against the bias-free truth (817 test roles)

| Group | Picked into top 5 | Picked when truly top 5 |
|---|---|---|
| Women | 0.322 | 0.736 |
| Men | 0.339 | 0.755 |
| Women with a career break | 0.367 | 0.750 |
| Women without a break | 0.315 | 0.732 |
| Men with a career break (19 people) | 0.493 | **0.938** |
| Men without a break | 0.328 | 0.747 |

The model choice already reflects this: the production variant was picked because its gap between women and men is the smallest (0.019). The other variants' gaps were 0.092 with raw ratings, 0.063 with corrected ratings only, and 0.023 with no ratings.

---

## 4. Issues and recommended fixes

| # | Issue | Recommended fix | Effort |
|---|---|---|---|
| 1 | Missing ratings cost 11 points | Use the "No past ratings" model, which is already trained (NDCG 0.854, gender gap 0.023), for candidates without history. Or fill missing ratings with the company average and add a separate "has history" flag | Small |
| 2 | Unverified skill claims are rewarded | Count an unverified, unevidenced level only up to the role's required level. Add a "higher is better" constraint on `verified_share` | Small (retrain) |
| 3 | Leave rule is all-or-nothing | Block when leave covers more than about 20% of the role, or more than 2 weeks in month 1. Otherwise warn and ask the head to plan cover. Turn a long leave later in the role into a blocker or require manager confirmation | Small |
| 4 | Corrected rating reveals gender | Show the raw rating, or only a band (High / Typical / Low), on the card. Keep the corrected value inside the model | Very small |
| 5 | Career break counts against experience | Let a returner's break count towards the minimum-experience tolerance, for example up to 1 extra year, with a warning instead of a block | Small |
| 6 | Returners lose project-history features | Measure history per *active* year (excluding long leave), not as a lifetime count | Medium (retrain) |
| 7 | Age: over-qualification penalty; age bias never corrected | Add a "more is never worse" constraint on `exp_gap` and `level`. Add age bands to the rating audit once 45+ cases exist. Show the age-band ratio in the live monitor | Small |
| 8 | Over-correction for men with breaks | Estimate a gender × career-break term in the rating audit instead of two separate shifts | Small |
| 9 | Live monitor checks gender only | Extend it to career break, age band, location and work mode, which these tests showed are worth watching | Small |

None of these are implemented yet. The tests are repeatable, so each fix can be checked by re-running `tests.fairness_audit` and comparing with these numbers.

---

## 5. Validation and testing in FairDecide AI

### 5.1 Data validation

| Check | What it catches | Where |
|---|---|---|
| Schema constraints | Valid levels, statuses, allocation %, request sources, dates; foreign keys | `db/schema.sql` |
| Point-in-time features | Each training row only sees skills, projects, ratings and certificates known *on that date*, so there is no leakage from the future | `backend/engine/features.py` |
| Preprocessing report | Rows per split, success rate, missing values and correlation per feature; confirms protected attributes are excluded | `backend/ml/artifacts/preprocessing_report.md` |
| Data-quality issues | Planted and detected: 343 skills claimed but not evidenced, 286 missing proficiency, 68 skill years above career length, 16 inconsistent experience records, 4 certificates with swapped dates, 4 missing emails. Each appears as a **flag on the candidate card**, and a missing proficiency **blocks** the candidate | `data/_ground_truth/data_quality_issues.csv`, `recommender._card` |

### 5.2 Model validation

| Check | Result |
|---|---|
| Time-based split (no shuffling) | Train 2018–23 (2,636 rows) · Validation 2024 (819) · Test 2025–26 (1,150) |
| Discrimination | Test AUC **0.808** (baseline formula 0.750) |
| Calibration | Brier score 0.178. Expected calibration error (ECE) 0.026. Calibration method chosen by 5-fold CV on 2024 |
| Classification | **F1 0.722** (precision 0.627, recall 0.852). The cut-off of 0.30 is chosen on 2024 and applied unchanged to 2025–26. F1 by gender: women 0.711, men 0.727 |
| Ranking vs the truth (817 roles) | **NDCG@10 0.902**, Precision@5 0.749. Baseline 0.879 / 0.735; random 0.56 / 0.37 |
| Variant comparison | Raw ratings / bias-corrected / bias-corrected + reweighing / no ratings. The production model has the smallest gender gap among variants within 0.01 NDCG of the best |
| Monotone constraints | Skill coverage, domain projects, past rating, similarity and certificates can only raise the score; skill gap and overload can only lower it |
| Retrain safety | Retraining is deterministic (seed 17). The model hash and calibrator were confirmed unchanged after the F1 update |

### 5.3 Fairness validation

| Check | When it runs |
|---|---|
| Rating bias audit (regression with confidence intervals) followed by correction of all 4,605 ratings | Offline, before training (`backend/ml/debias.py`) |
| Kamiran–Calders reweighing by gender × career break | During training |
| Equal-opportunity gap and F1 by gender | Every training run (`evaluation_report.md`) |
| **Four-fifths check on every shortlist** shown to managers | Live, on every recommendation |
| **Stress tests in this report:** 22 counterfactual twin scenarios plus 2 leave-consistency checks, group outcomes on live demands, replay against the truth, proxy test | On demand (`tests/fairness_audit.py`) |

### 5.4 Explainability and human oversight

- **What each candidate card shows:**
  - a SHAP breakdown in percentage points, grouped into 7 factors;
  - a plain-English explanation;
  - a confidence level;
  - data-quality flags;
  - near misses, with "why not this person?".
- **Approval before anything is assigned:**
  - Nothing is assigned automatically. The project head requests, approvers approve or reject (a rejection must include a reason), and only then does Send update the database and email the person.
  - A request for someone found through an eligibility check must include a written reason, and is labelled "Hand-picked after eligibility check" for approvers.
- **Audit trail:** every decision is stored with the full recommended list and explanations. Choosing someone outside the shortlist is recorded as "modified".

### 5.5 Application testing

| Suite | Scope | Last result |
|---|---|---|
| `tests/e2e_flow.py` | **76 API checks** across the whole workflow: login, permissions, recommendations, explanations, what-if, eligibility, approval chain, rejection reasons, send, database update, email, live events, audit trail, suggestions, the admin role (add employee, hire or promote a manager, handover) and demo reset | 76 / 76 pass |
| `tests/ui_flow.py` + admin browser check | Playwright drives the real web app through login, shortlist, approval and admin screens and records browser errors | Pass, no browser errors |
| Isolated test environment | Tests run on a cloned `fairdecide_test` database, a separate API, a separate mailbox and a separate frontend, which are removed afterwards. Live demo data is never touched | Used for every run |
| `tests/fairness_audit.py` (new) | Fairness stress tests: read-only, about 2.5 minutes | Results above |

---

## 6. Limitations

- **The data is synthetic.** Its biases were injected on purpose, which is what makes a bias-free truth possible. Real company data will have biases we did not anticipate.
- **Some groups are small:** 19 men with a career break, 55 eligible people aged 40–49, and 69 remote workers. Treat their ratios as warning signs, not proof.
- **Age is measured today** in the replay, not at the time of each assignment.
- **Gender is recorded as two values.** Non-binary employees and other protected groups (disability, caste, religion) are not in the data and therefore not tested.
- **Twins change one thing at a time.** Real disadvantages combine, for example a woman returning from a break with fewer projects and fewer ratings, and the combined effect can be larger than any single row above.
