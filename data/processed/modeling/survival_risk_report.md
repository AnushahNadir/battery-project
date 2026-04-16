# Survival Risk Report

**Model:** kaplan_meier_grouped
**Configured method:** kaplan_meier
**Horizon:** 20 cycles

## What this means (simple)

- `hazard_prob` = chance the battery fails *at this cycle* (given it survived before).
- `failure_prob_horizon` = chance the battery fails within the next **20 cycles**.
- This is a risk signal, not a causal explanation.

## Data summary

- Rows: 2422
- Batteries: 7
- Events observed: 6
- Event rate: 0.2477%

## Risk distribution (by row)

| Category | Count | % |
|---|---:|---:|
| LOW | 1037 | 42.8% |
| MEDIUM | 94 | 3.9% |
| HIGH | 1291 | 53.3% |

## Kaplan-Meier Groups

- Survival curves are estimated per temperature group (`room`, `hot`, `cold`).
- Horizon failure risk is computed as `1 - S(t+h)/S(t)`.