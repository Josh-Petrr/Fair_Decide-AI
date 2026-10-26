# Model evaluation report

Train 2,636 rows (2018-2023) | Validation 819 (2024) | Test 1,150 (2025-26)

## 1. Success prediction on the test period (labels = historical ratings, which contain bias)

| model                       |   AUC |   Brier |   ECE_raw |   ECE_final | calibration   |   trees |
|:----------------------------|------:|--------:|----------:|------------:|:--------------|--------:|
| Raw ratings                 | 0.807 |   0.184 |     0.035 |       0.07  | isotonic      |     197 |
| Bias-corrected ratings      | 0.806 |   0.18  |     0.025 |       0.025 | none          |     236 |
| Bias-corrected + reweighing | 0.808 |   0.178 |     0.026 |       0.026 | none          |     192 |
| No past ratings             | 0.772 |   0.194 |     0.028 |       0.028 | none          |     140 |
| Baseline formula            | 0.75  | nan     |   nan     |     nan     | nan           |     nan |

Calibration chosen by 5-fold CV ECE on 2024: Raw ratings: none=0.086, sigmoid=0.084, isotonic=0.070; Bias-corrected ratings: none=0.080, sigmoid=0.105, isotonic=0.088; Bias-corrected + reweighing: none=0.082, sigmoid=0.094, isotonic=0.090; No past ratings: none=0.083, sigmoid=0.088, isotonic=0.083

## 2. Ranking quality on 817 test roles vs. true (bias-free) suitability

| method                      |   NDCG@10 |   Precision@5 (true top-5) |   Avg pool |
|:----------------------------|----------:|---------------------------:|-----------:|
| Baseline formula            |     0.879 |                      0.735 |     15.009 |
| Bias-corrected + reweighing |     0.902 |                      0.749 |     15.009 |
| Bias-corrected ratings      |     0.899 |                      0.736 |     15.009 |
| No past ratings             |     0.854 |                      0.66  |     15.009 |
| Random                      |     0.547 |                      0.366 |     15.009 |
| Raw ratings                 |     0.892 |                      0.735 |     15.009 |

## 3. Fairness of the top-5 shortlist by gender

|                                           |   selection_rate |   selected_when_truly_top5 |
|:------------------------------------------|-----------------:|---------------------------:|
| ('Bias-corrected + reweighing', 'Female') |            0.322 |                      0.736 |
| ('Bias-corrected + reweighing', 'Male')   |            0.339 |                      0.755 |
| ('Bias-corrected ratings', 'Female')      |            0.312 |                      0.695 |
| ('Bias-corrected ratings', 'Male')        |            0.345 |                      0.758 |
| ('No past ratings', 'Female')             |            0.332 |                      0.675 |
| ('No past ratings', 'Male')               |            0.334 |                      0.652 |
| ('Raw ratings', 'Female')                 |            0.288 |                      0.68  |
| ('Raw ratings', 'Male')                   |            0.358 |                      0.764 |

Equal-opportunity gap: Raw ratings = 0.083, Bias-corrected ratings = 0.063, Bias-corrected + reweighing = 0.019, No past ratings = 0.023

**Production model: Bias-corrected + reweighing**

## 4. Feature importance (gain) of the production model

|                 |   share |
|:----------------|--------:|
| past_rating     |   0.19  |
| must_surplus    |   0.16  |
| exp_gap         |   0.124 |
| must_coverage   |   0.081 |
| nice_coverage   |   0.071 |
| must_gap        |   0.068 |
| exp_years       |   0.059 |
| sim_top3        |   0.039 |
| sim_max         |   0.031 |
| domain_projects |   0.028 |
| verified_share  |   0.022 |
| must_held       |   0.019 |
| overloaded      |   0.017 |
| level           |   0.017 |
| load_after      |   0.017 |
| total_projects  |   0.014 |
| alloc           |   0.012 |
| load_before     |   0.01  |
| pcert_count     |   0.009 |
| mcert_ok        |   0.009 |
| concurrent      |   0.003 |
| evidenced_share |   0.001 |
| same_family     |   0.001 |
| must_unknown    |   0     |