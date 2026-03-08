"""SHAP explainability helpers for tree-based ML models."""

from __future__ import annotations

from typing import Any

import numpy as np
import shap


def _resolve_tree_model(model: Any) -> Any:
    """Extract the underlying tree estimator when wrapped by calibration."""
    if hasattr(model, "calibrated_classifiers_") and model.calibrated_classifiers_:
        calibrated = model.calibrated_classifiers_[0]
        if hasattr(calibrated, "estimator"):
            return calibrated.estimator
        if hasattr(calibrated, "base_estimator"):
            return calibrated.base_estimator
    return model


def compute_shap_values(model: Any, X: np.ndarray) -> np.ndarray:
    """Compute SHAP values for samples using a tree explainer."""
    tree_model = _resolve_tree_model(model)
    explainer = shap.TreeExplainer(tree_model)
    shap_values = explainer.shap_values(X)

    if isinstance(shap_values, list):
        if len(shap_values) > 1:
            return np.asarray(shap_values[1], dtype=float)
        return np.asarray(shap_values[0], dtype=float)

    array_values = np.asarray(shap_values, dtype=float)
    if array_values.ndim == 3 and array_values.shape[-1] > 1:
        return array_values[:, :, 1]
    return array_values


def get_top_features(shap_values: np.ndarray, feature_names: list[str], n: int = 3) -> list[dict[str, Any]]:
    """Return top-N features by absolute SHAP magnitude for one sample."""
    values = np.asarray(shap_values, dtype=float)
    if values.ndim == 2:
        if values.shape[0] != 1:
            raise ValueError("Expected a single-sample SHAP vector.")
        values = values[0]
    if values.ndim != 1:
        raise ValueError("SHAP input must be a 1D vector for one sample.")
    if len(feature_names) != values.shape[0]:
        raise ValueError("feature_names length must match SHAP vector length.")

    top_indices = np.argsort(np.abs(values))[::-1][:n]
    top_features: list[dict[str, Any]] = []
    for idx in top_indices:
        shap_value = float(values[idx])
        top_features.append(
            {
                "feature": feature_names[idx],
                "shap_value": shap_value,
                "direction": "risk" if shap_value > 0 else "safe",
            }
        )
    return top_features
