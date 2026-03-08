# OSS Pulse Architecture

## System Goal

OSS Pulse predicts disruption risk for critical open source dependencies before failures become operational incidents. The architecture prioritizes early warning, explainability, and reproducible weekly scoring.

## End-to-End Data Flow

```text
GitHub REST API + Google News RSS
              |
              v
+-------------------------------+
| Module 1: Ingestion           |
| backend/scrapers/*.py         |
+-------------------------------+
              |
              v
+-------------------------------+
| Module 2: Pipeline            |
| backend/pipeline/*.py         |
| (snapshots -> features)       |
+-------------------------------+
              |
              v
+-------------------------------+
| Module 3: ML Training         |
| backend/ml/data.py            |
| backend/ml/train.py           |
| docs/labeled_events.csv       |
+-------------------------------+
              |
              v
+-------------------------------+
| Module 4: Inference + SHAP    |
| backend/ml/scorer.py          |
| backend/ml/inference.py       |
| backend/ml/explain.py         |
+-------------------------------+
              |
              v
+-------------------------------+
| Module 5: API                 |
| backend/api/main.py           |
| backend/api/schemas.py        |
+-------------------------------+
              |
              v
+-------------------------------+
| Module 6: Frontend Dashboard  |
| frontend/src/pages/*          |
| frontend/src/components/*     |
+-------------------------------+
```

## Module 1: Ingestion (Scrapers)

**Files:**

- `backend/scrapers/github.py`
- `backend/scrapers/news.py`
- `backend/scrapers/store.py`

**Responsibilities:**

- Pull contributor, commit, issue, and release telemetry from GitHub.
- Pull project-related news and compute lightweight sentiment.
- Persist raw scrape payloads to snapshots for auditability.

**Key design decisions:**

- Keep full raw JSON (`snapshots.raw_json`) before feature transformation.
- Apply retry logic for transient API failures and rate-limit behavior.
- Treat news as a separate signal stream for non-code ecosystem risk.

## Module 2: Pipeline and Orchestration

**Files:**

- `backend/pipeline/features.py`
- `backend/pipeline/scheduler.py`
- `backend/pipeline/bus_factor.py`

**Responsibilities:**

- Convert raw snapshots into weekly feature vectors.
- Orchestrate scrape -> news -> feature extraction -> scoring.
- Run on schedule (Monday 03:00 UTC) and on-demand trigger.

**Key design decisions:**

- Weekly cadence balances signal freshness and noise reduction.
- Per-project try/except boundaries prevent one failure from stopping global runs.
- Deterministic feature schema keeps training and inference aligned.

## Module 3: ML Training

**Files:**

- `backend/ml/data.py`
- `backend/ml/train.py`
- `docs/labeled_events.csv`
- `docs/labeling_methodology.md`

**Responsibilities:**

- Load labeled windows and align them with engineered features.
- Train baseline Logistic Regression and production XGBoost models.
- Evaluate with ROC-AUC, F1, precision, and recall.

**Key design decisions:**

- Use stratified splitting and 5-fold validation due to class imbalance.
- Keep a linear baseline for interpretability and regression checks.
- Persist models as versioned artifacts under `backend/ml/models/`.

## Module 4: Inference and Explainability

**Files:**

- `backend/ml/scorer.py`
- `backend/ml/inference.py`
- `backend/ml/explain.py`

**Responsibilities:**

- Load latest feature row for a project and generate risk score.
- Apply fallback heuristic if model file is missing or inference fails.
- Compute SHAP feature contributions and top signals.

**Key design decisions:**

- Fallback scoring guarantees API continuity during model outages.
- Score normalization enforces integer range 0-100.
- SHAP top features are persisted with each risk score for UI explainability.

## Module 5: API Layer

**Files:**

- `backend/api/main.py`
- `backend/api/schemas.py`

**Responsibilities:**

- Expose health, project catalog, project detail, risk-score, and pipeline trigger endpoints.
- Enforce normalized response contracts (`{ ok, data }` or error payload).
- Bridge frontend requests to current DB state and scoring pipeline.

**Key design decisions:**

- Typed response schemas ensure consistent frontend contract behavior.
- Route-level error envelopes simplify client-side handling.
- Trigger endpoint supports manual demo and operational verification.

## Module 6: Frontend Dashboard

**Files:**

- `frontend/src/pages/Overview.jsx`
- `frontend/src/pages/ProjectDetail.jsx`
- `frontend/src/components/*`
- `frontend/src/lib/api.js`

**Responsibilities:**

- Display ranked project risk overview.
- Provide per-project deep dive with trends, SHAP explanations, and news context.
- Translate API responses into interactive operational views.

**Key design decisions:**

- Overview prioritizes triage speed with risk-first ranking.
- Detail view surfaces both historical signals and explanation context.
- Shared API client centralizes network error normalization.

## Database Schema Summary

| Table | Purpose | Key Columns |
|---|---|---|
| `projects` | Canonical monitored repository catalog. | `id`, `owner`, `repo`, `name`, `html_url`, `created_at` |
| `snapshots` | Raw scrape payload per project run. | `id`, `project_id` (FK), `scraped_at`, `raw_json` |
| `features` | Weekly engineered risk features. | `id`, `project_id` (FK), `week_start`, 7 feature columns |
| `risk_scores` | Scored outputs + explanation signals. | `id`, `project_id` (FK), `scored_at`, `score`, `top_feature_1..3` |
| `news_items` | News evidence stream with sentiment. | `id`, `project_id` (FK), `title`, `url`, `published_at`, `sentiment_score` |

## ML Lifecycle Details

```text
Raw Snapshots + News
        |
        v
Feature Engineering (7 weekly signals)
        |
        v
Labeled Window Join (48 rows total)
        |
        v
Training (LR baseline + XGBoost)
        |
        v
Model Serialization (lr_v1.pkl, xgb_v1.pkl)
        |
        v
Inference per Project
        |
        +--> Risk Score (0-100)
        +--> SHAP Top Signals
```

- **Feature engineering:** `backend/pipeline/features.py` computes fixed numerical signals from code activity and news context.
- **Training:** `backend/ml/train.py` uses stratified holdout + cross-validation and class imbalance controls.
- **Inference:** `backend/ml/scorer.py` loads latest features and executes model prediction through `backend/ml/inference.py`.
- **SHAP explanation:** `backend/ml/explain.py` surfaces top feature-level contributors for each risk score.

## Operational Notes

- Scheduler executes every Monday at 03:00 UTC through APScheduler.
- Manual pipeline execution is available through `POST /pipeline/trigger`.
- API contract consistency is maintained via typed Pydantic schemas in `backend/api/schemas.py`.
