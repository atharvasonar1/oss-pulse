# OSS Pulse

OSS Pulse is an open source dependency health monitor designed to track GitHub activity signals and estimate disruption risk for projects Red Hat depends on.

## Repository Layout

- `frontend/`: React + Vite dashboard shell.
- `backend/`: Scrapers, pipeline, ML, API, and DB module shells.
- `scripts/`: Utility scripts.
- `infra/`: Deployment configuration shells.
- `docs/`: Architecture, contracts, and project inventory.

## Prerequisites

- Node.js 18+
- Python 3.11+
- `pip`

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Backend Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Current Status

Initial scaffold only. No application logic has been implemented yet.
