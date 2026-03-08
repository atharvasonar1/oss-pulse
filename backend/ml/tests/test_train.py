from __future__ import annotations

import pickle

import numpy as np

from backend.ml.data import REQUIRED_LABEL_COLUMNS, load_from_csv
from backend.ml.train import get_feature_names, train_logistic_regression


def _synthetic_xy() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed=42)
    X = rng.normal(loc=0.0, scale=1.0, size=(200, 7))
    noise = rng.normal(loc=0.0, scale=0.3, size=200)
    logits = X[:, 0] * 1.5 + X[:, 1] * 0.8 - X[:, 3] * 0.4 + noise
    y = (logits > np.median(logits)).astype(int)
    return X, y


def test_train_logistic_regression_returns_required_metric_keys(tmp_path) -> None:
    X, y = _synthetic_xy()
    model_path = tmp_path / "lr_v1.pkl"
    metrics = train_logistic_regression(X, y, model_path=model_path)

    required_keys = {"auc", "f1", "precision", "recall", "model_path"}
    assert required_keys.issubset(metrics.keys())
    assert isinstance(metrics["auc"], float)
    assert isinstance(metrics["f1"], float)


def test_serialized_model_file_exists_after_training(tmp_path) -> None:
    X, y = _synthetic_xy()
    model_path = tmp_path / "lr_v1.pkl"

    train_logistic_regression(X, y, model_path=model_path)
    assert model_path.exists()


def test_loaded_model_can_predict_and_predict_proba(tmp_path) -> None:
    X, y = _synthetic_xy()
    model_path = tmp_path / "lr_v1.pkl"
    train_logistic_regression(X, y, model_path=model_path)

    with model_path.open("rb") as handle:
        model = pickle.load(handle)

    sample = X[:5]
    preds = model.predict(sample)
    proba = model.predict_proba(sample)

    assert preds.shape == (5,)
    assert proba.shape == (5, 2)


def test_get_feature_names_returns_exactly_seven_strings() -> None:
    names = get_feature_names()
    assert isinstance(names, list)
    assert len(names) == 7
    assert all(isinstance(name, str) for name in names)


def test_load_from_csv_returns_dataframe_with_required_columns() -> None:
    df = load_from_csv("docs/labeled_events.csv")
    assert set(REQUIRED_LABEL_COLUMNS).issubset(df.columns)
    assert len(df) >= 40
