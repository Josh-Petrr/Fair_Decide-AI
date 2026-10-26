# Preprocessing report

Rows: 4,605 completed & rated assignments

| Split | Rows | Period | Success rate (rating >= 4) |
|---|---|---|---|
| train | 2,636 | 2018-06-09 .. 2023-12-28 | 44.2% |
| valid | 819 | 2024-01-01 .. 2024-12-28 | 44.0% |
| test | 1,150 | 2025-01-02 .. 2026-07-23 | 47.5% |

| Feature | Missing | Mean | Corr. with success |
|---|---|---|---|
| must_coverage | 0.0% | 0.78 | +0.32 |
| must_held | 0.0% | 0.82 | +0.31 |
| must_gap | 0.0% | 0.48 | -0.30 |
| must_surplus | 0.0% | 1.41 | +0.29 |
| must_unknown | 0.0% | 0.01 | +0.04 |
| nice_coverage | 13.9% | 0.58 | +0.20 |
| exp_years | 0.0% | 6.17 | +0.07 |
| exp_gap | 0.0% | 2.58 | +0.15 |
| level | 0.0% | 3.43 | +0.06 |
| same_family | 0.0% | 0.88 | +0.17 |
| domain_projects | 0.0% | 0.58 | +0.15 |
| total_projects | 0.0% | 3.08 | +0.10 |
| past_rating | 30.7% | 3.42 | +0.37 |
| sim_max | 30.9% | 0.59 | +0.18 |
| sim_top3 | 30.9% | 0.53 | +0.18 |
| mcert_ok | 0.0% | 0.95 | +0.05 |
| pcert_count | 0.0% | 0.09 | +0.07 |
| verified_share | 0.0% | 0.59 | +0.07 |
| evidenced_share | 0.0% | 0.56 | +0.13 |
| load_before | 0.0% | 23.89 | -0.03 |
| load_after | 0.0% | 106.54 | +0.01 |
| concurrent | 0.0% | 0.48 | -0.02 |
| overloaded | 0.0% | 0.20 | -0.04 |
| alloc | 0.0% | 82.65 | +0.05 |

Protected attributes excluded: gender, date_of_birth, age_band, career_break_months