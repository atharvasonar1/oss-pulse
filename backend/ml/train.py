"""Training utilities for the baseline logistic regression model."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split

from backend.ml.data import FEATURE_COLUMNS


DEFAULT_MODEL_PATH = Path("backend/ml/models/lr_v1.pkl")


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
