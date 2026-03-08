"""Training utilities for the baseline logistic regression model."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split

from backend.ml.data import FEATURE_COLUMNS


DEFAULT_MODEL_PATH = Path("backend/ml/models/lr_v1.pkl")
DEFAULT_XGB_MODEL_PATH = Path("backend/ml/models/xgb_v1.pkl")


def get_feature_names() -> list[str]:
    """Return the canonical ordered list of training features."""
    return list(FEATURE_COLUMNS)


def _validate_xy(X: np.ndarray, y: np.ndarray) -> None:
    if X.ndim != 2:
        raise ValueError("X must be a 2D array.")
    if y.ndim != 1:
        raise ValueError("y must be a 1D array.")
    if X.shape[0] != y.shape[0]:
        raise ValueError("X and y must have the same number of rows.")
    if X.shape[1] != len(FEATURE_COLUMNS):
        raise ValueError(f"X must have exactly {len(FEATURE_COLUMNS)} columns.")

    unique_labels = np.unique(y)
    if len(unique_labels) < 2:
        raise ValueError("y must contain at least two classes.")

    label_counts = np.bincount(y.astype(int))
    if len(label_counts) < 2 or np.any(label_counts[:2] < 2):
        raise ValueError("Each class in y must have at least 2 samples.")


def _build_xgb_estimator(scale_pos_weight: float) -> Any:
    """Build XGBoost estimator, falling back when OpenMP runtime is unavailable."""
    try:
        from xgboost import XGBClassifier  # type: ignore

        return XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric="logloss",
            scale_pos_weight=scale_pos_weight,
            random_state=42,
        )
    except Exception:
        # Environment fallback for local runtime setups missing libomp.
        return RandomForestClassifier(
            n_estimators=200,
            max_depth=4,
            class_weight={0: 1.0, 1: float(scale_pos_weight)},
            random_state=42,
        )


def train_logistic_regression(X: np.ndarray, y: np.ndarray, model_path: str | Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    """Train, evaluate, and serialize a baseline logistic regression model."""
    _validate_xy(X, y)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    model = LogisticRegression(class_weight="balanced", max_iter=2000, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    auc = float(roc_auc_score(y_test, y_proba))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_validate(
        LogisticRegression(class_weight="balanced", max_iter=2000, random_state=42),
        X,
        y,
        cv=cv,
        scoring={"auc": "roc_auc", "f1": "f1"},
        n_jobs=None,
    )
    cv_auc = float(np.mean(cv_scores["test_auc"]))
    cv_f1 = float(np.mean(cv_scores["test_f1"]))

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as handle:
        pickle.dump(model, handle)

    return {
        "auc": auc,
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "cv_auc": cv_auc,
        "cv_f1": cv_f1,
        "model_path": str(model_path),
    }


def train_xgboost(X: np.ndarray, y: np.ndarray, model_path: str | Path = DEFAULT_XGB_MODEL_PATH) -> dict[str, Any]:
    """Train, evaluate, calibrate, and serialize an XGBoost classifier."""
    _validate_xy(X, y)

    negatives = int((y == 0).sum())
    positives = int((y == 1).sum())
    scale_pos_weight = negatives / max(positives, 1)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )

    base_model = _build_xgb_estimator(scale_pos_weight)
    calibrated_model = CalibratedClassifierCV(estimator=base_model, method="sigmoid", cv=5)
    calibrated_model.fit(X_train, y_train)

    y_pred = calibrated_model.predict(X_test)
    y_proba = calibrated_model.predict_proba(X_test)[:, 1]

    auc = float(roc_auc_score(y_test, y_proba))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_estimator = CalibratedClassifierCV(estimator=_build_xgb_estimator(scale_pos_weight), method="sigmoid", cv=5)
    cv_scores = cross_validate(
        cv_estimator,
        X,
        y,
        cv=cv,
        scoring={"auc": "roc_auc", "f1": "f1"},
        n_jobs=None,
    )
    cv_auc = float(np.mean(cv_scores["test_auc"]))
    cv_f1 = float(np.mean(cv_scores["test_f1"]))

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with model_path.open("wb") as handle:
        pickle.dump(calibrated_model, handle)

    return {
        "auc": auc,
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "cv_auc": cv_auc,
        "cv_f1": cv_f1,
        "model_path": str(model_path),
    }
