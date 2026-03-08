# OSS Pulse

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white) ![Tests](https://img.shields.io/badge/tests-80%20passing-16a34a) ![License](https://img.shields.io/badge/license-MIT-blue)

**OSS Pulse** is an Open Source Dependency Health Monitor that predicts disruption risk across strategic OSS repositories used in enterprise Linux and cloud platforms. Built for Red Hat-style platform engineering and portfolio governance, it transforms raw community telemetry into actionable risk scores before dependency failures become production incidents.

## Problem

When a critical open source dependency is suddenly abandoned, sabotaged, or overwhelmed, downstream enterprise platforms inherit risk immediately: delayed patches, broken release trains, and emergency migration work. For organizations with broad OSS footprints, that disruption can cascade across security, SRE, and product teams in days.

Most current approaches do not scale. Manual monitoring is inconsistent across hundreds of repositories, and star counts are a weak proxy for project health because popularity does not capture maintainer load, contributor concentration, release cadence, or issue closure behavior. Recent ecosystem incidents demonstrate this gap clearly: **Log4Shell** (security shock in a widely used dependency), **left-pad** (package removal blast radius), and **event-stream** (supply-chain compromise through maintainer trust).

## Solution

OSS Pulse continuously ingests GitHub and news signals, converts them into weekly feature vectors, and scores each project for disruption likelihood using explainable machine learning. The system is designed to provide early warning 3-6 months before major dependency instability becomes obvious.

The model monitors seven signals:

1. `contributor_delta_pct`: Change in active contributor count between prior and recent windows.
2. `commit_velocity_delta`: Change in commit activity between two rolling time periods.
3. `issue_close_rate`: Proportion of issues that are closing vs total issue volume.
4. `bus_factor`: Number of top contributors needed to account for 50% of commits.
5. `maintainer_inactivity_days`: Maximum inactivity period among core maintainers.
6. `news_sentiment_avg`: Rolling sentiment score from project-related external news.
7. `days_since_last_release`: Time elapsed since the latest tagged release.

## Architecture

```text
+------------+     +----------------+     +-------------------+     +----------------+
| GitHub API | --> | Scraper Layer  | --> | Feature Extractor | --> | XGBoost Model  |
+------------+     +----------------+     +-------------------+     +----------------+
       |                    |                        |                         |
       |                    v                        v                         v
       |             +----------------+      +----------------+        +----------------+
       +-----------> | Snapshots DB   |      | Features DB    |        | Risk Scores DB |
                     +----------------+      +----------------+        +----------------+
                                                                              |
                                                                              v
                                                                      +----------------+
                                                                      | FastAPI API    |
                                                                      +----------------+
                                                                              |
                                                                              v
                                                                      +----------------+
                                                                      | React Dashboard|
                                                                      +----------------+
```

**GitHub and news ingestion:** `backend/scrapers/github.py` and `backend/scrapers/news.py` collect repository activity and external signals. This approach keeps raw evidence in storage before feature transformations, which supports reproducibility and debugging.

**Feature engineering pipeline:** `backend/pipeline/features.py` computes fixed weekly features from snapshots and news. Weekly extraction provides consistent, model-ready training and inference inputs.

**Model training and scoring:** `backend/ml/train.py` trains Logistic Regression and XGBoost baselines, while `backend/ml/scorer.py` handles inference and fallback scoring. XGBoost was selected for non-linear interactions across mixed operational and social signals.

**API serving:** `backend/api/main.py` exposes normalized response contracts (`{ ok, data }`) for dashboard consumption and pipeline triggers. FastAPI was chosen for typed schemas, performance, and concise route definitions.

**Frontend decision surface:** `frontend/src/pages/Overview.jsx` and `frontend/src/pages/ProjectDetail.jsx` surface ranked risk, trends, and SHAP explanations for analysts and platform leads. React + Vite keeps iteration fast while preserving a modular component model.

## Demo

![Overview Dashboard](docs/screenshots/oss-dashboard.png)

![Detail View](docs/screenshots/Card_ss.png)

How to read the dashboard:

1. Open the **Overview** page and sort projects by highest risk score.
2. Focus on projects in red-tier ranges first to prioritize triage.
3. Open a project detail view to inspect contributor trend, issue flow, and recent news.
4. Review the SHAP explanation panel to see which signals pushed risk up or down.

What SHAP explains:

- SHAP identifies the top feature contributions for a given prediction, not just a raw score.
- Positive SHAP contributions indicate risk-driving signals (for example maintainer inactivity).
- Negative SHAP contributions indicate stabilizing signals (for example improving closure rate).

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

### Environment Variables

Create a `.env` in repo root with:

```bash
GITHUB_TOKEN=your_github_token
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/oss_pulse
SECRET_KEY=replace_with_a_random_secret
```

### Setup and Run

```bash
# 1) Clone
git clone https://github.com/atharvasonar1/oss-pulse.git
cd oss-pulse

# 2) Backend dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3) Run migrations
alembic upgrade head

# 4) Seed project inventory
python scripts/seed.py

# 5) Start backend API
uvicorn backend.api.main:app --reload --port 8000
```

In a second terminal:

```bash
# 6) Frontend dependencies + dev server
cd frontend
npm install
npm run dev
```

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health and version check. |
| `GET` | `/projects` | List all tracked repositories. |
| `GET` | `/projects/{project_id}` | Fetch one project by numeric ID. |
| `GET` | `/projects/{project_id}/risk-score` | Score a project and return score + top features. |
| `POST` | `/pipeline/trigger` | Execute the scrape -> features -> scoring pipeline immediately. |

## Model

Training data currently includes **48 labeled windows**: **15 disruption cases** and **33 healthy windows** from infrastructure-relevant OSS projects.

- **Baseline model:** Logistic Regression with class balancing (`class_weight='balanced'`) and target ROC-AUC > 0.70.
- **Production model:** XGBoost with probability calibration and SHAP feature attribution for explainability.
- **Primary metric:** ROC-AUC is prioritized over raw accuracy because the class distribution is imbalanced and the goal is ranking high-risk projects reliably.
- **Imbalance handling:** Stratified train/test splitting, 5-fold cross-validation, model weighting (`class_weight` and `scale_pos_weight`), and threshold-aware evaluation.

## Roadmap

Near-term:

1. Real-time alerting for sharp week-over-week risk changes.
2. Expansion from seed repositories to a larger dependency universe.
3. Slack and JIRA integration for automated triage workflows.

Longer-term:

1. Fine-tuned LLM analysis of commit messages and issue narratives for richer disruption context.
