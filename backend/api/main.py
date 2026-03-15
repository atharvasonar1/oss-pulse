"""FastAPI scaffold for OSS Pulse."""

from __future__ import annotations

from collections.abc import Generator
from difflib import get_close_matches

from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.schemas import (
    AnalyzeResponseSchema,
    ErrorResponse,
    ManifestMatchSchema,
    ProjectSchema,
    RiskHistoryPointSchema,
    RiskScoreSchema,
    SuccessResponse,
)
from backend.db.models import Project, RiskScore
from backend.db.session import get_session
from backend.ml.scorer import score_project
from backend.parsers.manifest import parse_go_mod, parse_package_json, parse_requirements_txt
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


@app.get(
    "/projects/{project_id}/risk-history",
    response_model=SuccessResponse[list[RiskHistoryPointSchema]],
    responses={404: {"model": ErrorResponse}},
)
def get_project_risk_history(
    project_id: int, db: Session = Depends(get_db)
) -> SuccessResponse[list[RiskHistoryPointSchema]] | JSONResponse:
    project = db.get(Project, project_id)
    if project is None:
        error = ErrorResponse(error="Project not found", status=404)
        return JSONResponse(status_code=404, content=error.model_dump())

    history_rows = (
        db.execute(
            select(RiskScore)
            .where(RiskScore.project_id == project_id)
            .order_by(RiskScore.scored_at.asc(), RiskScore.id.asc())
        )
        .scalars()
        .all()
    )
    payload = [RiskHistoryPointSchema(score=row.score, scored_at=row.scored_at) for row in history_rows]
    return SuccessResponse(data=payload)


@app.post(
    "/analyze",
    response_model=SuccessResponse[AnalyzeResponseSchema],
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def analyze_manifest(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> SuccessResponse[AnalyzeResponseSchema] | JSONResponse:
    filename = (file.filename or "").lower()
    if filename.endswith(".txt"):
        parser = parse_requirements_txt
    elif filename.endswith(".json"):
        parser = parse_package_json
    elif filename.endswith(".mod"):
        parser = parse_go_mod
    else:
        error = ErrorResponse(error="Unsupported file type", status=400)
        return JSONResponse(status_code=400, content=error.model_dump())

    try:
        decoded = (await file.read()).decode("utf-8")
        package_names = parser(decoded)
    except Exception:
        error = ErrorResponse(error="Unable to parse manifest file", status=422)
        return JSONResponse(status_code=422, content=error.model_dump())

    projects = db.execute(select(Project).order_by(Project.id.asc())).scalars().all()
    repo_lookup = {project.repo.lower(): project for project in projects}
    repo_names = list(repo_lookup.keys())

    matched: list[ManifestMatchSchema] = []
    unmatched: list[str] = []

    for package in package_names:
        closest = get_close_matches(package.lower(), repo_names, n=1, cutoff=0.6)
        if not closest:
            unmatched.append(package)
            continue

        project = repo_lookup[closest[0]]
        latest_risk = (
            db.execute(
                select(RiskScore)
                .where(RiskScore.project_id == project.id)
                .order_by(RiskScore.scored_at.desc(), RiskScore.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        top_features: list[str] = []
        if latest_risk is not None:
            for value in (latest_risk.top_feature_1, latest_risk.top_feature_2, latest_risk.top_feature_3):
                if value:
                    top_features.append(value)

        matched.append(
            ManifestMatchSchema(
                package=package,
                repo=project.repo,
                owner=project.owner,
                score=latest_risk.score if latest_risk else None,
                top_features=top_features,
            )
        )

    return SuccessResponse(data=AnalyzeResponseSchema(matched=matched, unmatched=unmatched))
