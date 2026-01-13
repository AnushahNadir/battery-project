# battery-project

The Main Project Repo



\# Battery Degradation Co-Scientist



A research-focused, reproducible pipeline for analyzing battery degradation using NASA dataset.



\## What this repo does

\- Loads battery cycling data (time-series)

\- Runs modular analyses (degradation modeling, anomaly detection, risk estimation)

\- Verifies consistency and uncertainty before reporting

\- Produces human-readable explanations grounded in references (RAG-ready)



\## What this repo does NOT do (non-claims)

\- Does not control hardware

\- Does not make safety-critical decisions

\- Does not claim real-world safety guarantees



\## Quick start

```bat

py -3.14 -m venv .venv

.venv\\Scripts\\activate

python -m src.main --help



