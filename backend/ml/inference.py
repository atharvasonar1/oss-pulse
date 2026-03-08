"""Inference utilities for risk scoring and explainability."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

from backend.ml.explain import compute_shap_values, get_top_features


def load_model(model_path: str) -> Any:
    """Load a serialized model from disk."""
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    with path.open("rb") as handle:
        return pickle.load(handle)


def predict_risk_score(model: Any, X_single: np.ndarray) -> int:
    """Predict calibrated risk score in the range 0-100."""
    array = np.asarray(X_single, dtype=float)
    if array.shape != (1, 7):
        raise ValueError("X_single must have shape (1, 7).")

    probability = float(model.predict_proba(array)[0, 1])
    score = int(round(probability * 100))
    return max(0, min(100, score))


def predict_with_explanation(model: Any, X_single: np.ndarray, feature_names: list[str]) -> dict[str, Any]:
    """Predict score and return top SHAP feature explanations."""
    score = predict_risk_score(model, X_single)
    shap_values = compute_shap_values(model, np.asarray(X_single, dtype=float))
    top_features = get_top_features(shap_values[0], feature_names, n=3)
    return {"score": score, "top_features": top_features}


def fallback_heuristic(features: dict[str, Any]) -> dict[str, Any]:
    """Rule-based fallback scoring when ML model inference is unavailable."""
    score = 50
    if float(features.get("bus_factor", 999)) <= 1:
        score += 20
    if float(features.get("maintainer_inactivity_days", 0)) >= 60:
        score += 15
    if float(features.get("contributor_delta_pct", 0.0)) <= -0.3:
        score += 15
    score = max(0, min(100, score))
    return {"score": int(score), "top_features": []}
