"""FastAPI scaffold for OSS Pulse."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.schemas import ErrorResponse, ProjectSchema, RiskScoreSchema, SuccessResponse
from backend.db.models import Project
from backend.db.session import get_session
from backend.ml.scorer import score_project
from backend.pipeline.scheduler import trigger_now


app = FastAPI(title="OSS Pulse API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session


@app.get("/health", response_model=SuccessResponse[dict[str, str]])
def health() -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(data={"status": "ok", "version": "0.1.0"})


@app.get("/projects", response_model=SuccessResponse[list[ProjectSchema]])
def list_projects(db: Session = Depends(get_db)) -> SuccessResponse[list[ProjectSchema]]:
    projects = db.execute(select(Project).order_by(Project.id.asc())).scalars().all()
    project_payload = [ProjectSchema.model_validate(project) for project in projects]
    return SuccessResponse(data=project_payload)


@app.get(
    "/projects/{project_id}",
    response_model=SuccessResponse[ProjectSchema],
    responses={404: {"model": ErrorResponse}},
)
def get_project(project_id: int, db: Session = Depends(get_db)) -> SuccessResponse[ProjectSchema] | JSONResponse:
    project = db.get(Project, project_id)
    if project is None:
        error = ErrorResponse(error="Project not found", status=404)
        return JSONResponse(status_code=404, content=error.model_dump())

    project_payload = ProjectSchema.model_validate(project)
    return SuccessResponse(data=project_payload)


@app.post("/pipeline/trigger", response_model=SuccessResponse[dict[str, object]])
def trigger_pipeline() -> SuccessResponse[dict[str, object]]:
    projects_processed = trigger_now()
    return SuccessResponse(data={"message": "Pipeline triggered", "projects_processed": projects_processed})


@app.get(
    "/projects/{project_id}/risk-score",
    response_model=SuccessResponse[RiskScoreSchema],
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def get_project_risk_score(
    project_id: int, db: Session = Depends(get_db)
) -> SuccessResponse[RiskScoreSchema] | JSONResponse:
    project = db.get(Project, project_id)
    if project is None:
        error = ErrorResponse(error="Project not found", status=404)
        return JSONResponse(status_code=404, content=error.model_dump())

    try:
        scored = score_project(db, project_id)
    except Exception:
        error = ErrorResponse(error="Scoring failed", status=500)
        return JSONResponse(status_code=500, content=error.model_dump())

    return SuccessResponse(data=RiskScoreSchema.model_validate(scored))
