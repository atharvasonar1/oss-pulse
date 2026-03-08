"""Pydantic schemas for API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from typing_extensions import Literal


class ProjectSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner: str
    repo: str
    name: str
    description: str | None
    html_url: str
    created_at: datetime


class TopFeatureSchema(BaseModel):
    feature: str
    shap_value: float
    direction: str


class RiskScoreSchema(BaseModel):
    score: int
    top_features: list[TopFeatureSchema]
    scored_at: datetime
    project_id: int


T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    ok: Literal[True] = True
    data: T


class ErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: str
    status: int
