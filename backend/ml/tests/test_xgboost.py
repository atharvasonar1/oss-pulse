from __future__ import annotations

import numpy as np

from backend.ml.inference import fallback_heuristic, load_model, predict_risk_score, predict_with_explanation
from backend.ml.train import get_feature_names, train_xgboost
from backend.ml.explain import get_top_features


def _synthetic_xy() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed=123)
    X = rng.normal(0.0, 1.0, size=(220, 7))
    linear = (1.3 * X[:, 0]) - (0.8 * X[:, 4]) + (0.5 * X[:, 5]) + rng.normal(0.0, 0.4, size=220)
    y = (linear > np.median(linear)).astype(int)
    return X, y


def test_train_xgboost_returns_required_metric_keys(tmp_path) -> None:
    X, y = _synthetic_xy()
    model_path = tmp_path / "xgb_v1.pkl"
    metrics = train_xgboost(X, y, model_path=model_path)

    required = {"auc", "f1", "precision", "recall", "cv_auc", "cv_f1", "model_path"}
    assert required.issubset(metrics.keys())


def test_xgboost_model_file_exists_and_loads(tmp_path) -> None:
    X, y = _synthetic_xy()
    model_path = tmp_path / "xgb_v1.pkl"
    train_xgboost(X, y, model_path=model_path)

    assert model_path.exists()
    loaded = load_model(str(model_path))
    assert loaded is not None


def test_predict_risk_score_returns_int_in_range(tmp_path) -> None:
    X, y = _synthetic_xy()
    model_path = tmp_path / "xgb_v1.pkl"
    train_xgboost(X, y, model_path=model_path)
    model = load_model(str(model_path))

    score = predict_risk_score(model, X[:1])
    assert isinstance(score, int)
    assert 0 <= score <= 100


def test_get_top_features_returns_three_dicts_with_required_keys() -> None:
    feature_names = get_feature_names()
    shap_vec = np.array([0.5, -0.3, 0.1, 0.0, -0.2, 0.05, 0.7])
    top = get_top_features(shap_vec, feature_names, n=3)

    assert len(top) == 3
    for item in top:
        assert set(item.keys()) == {"feature", "shap_value", "direction"}
        assert item["direction"] in {"risk", "safe"}


def test_fallback_heuristic_returns_elevated_score_for_high_risk_inputs() -> None:
    result = fallback_heuristic(
        {
            "bus_factor": 1,
            "maintainer_inactivity_days": 90,
            "contributor_delta_pct": 0.0,
        }
    )
    assert result["score"] == 85
    assert result["top_features"] == []


def test_predict_with_explanation_returns_score_and_top_features(tmp_path, monkeypatch) -> None:
    X, y = _synthetic_xy()
    model_path = tmp_path / "xgb_v1.pkl"
    train_xgboost(X, y, model_path=model_path)
    model = load_model(str(model_path))
    feature_names = get_feature_names()

    mock_shap_values = np.array([[0.4, -0.2, 0.1, 0.05, -0.1, 0.0, 0.3]])
    monkeypatch.setattr("backend.ml.inference.compute_shap_values", lambda _m, _x: mock_shap_values)

    output = predict_with_explanation(model, X[:1], feature_names)
    assert set(output.keys()) == {"score", "top_features"}
    assert isinstance(output["score"], int)
    assert isinstance(output["top_features"], list)
