import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.config import (
    ARTIFACTS_DIR,
    TARGET_FINISH_POSITION,
    TARGET_PODIUM,
    TARGET_TOP5,
    TARGET_WIN,
)
from ml.data_split import chronological_race_split
from ml.features.metadata import FEATURE_METADATA
from ml.validation.leakage_checks import validate_dataset_no_leakage, validate_feature_target_separation

logger = logging.getLogger(__name__)


def get_feature_columns(df: pd.DataFrame) -> List[str]:
    """Extract valid feature columns present in DataFrame and validate target separation."""
    feature_cols = [c for c in df.columns if c in FEATURE_METADATA]
    validate_feature_target_separation(feature_cols)
    return feature_cols


def train_win_probability_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[Pipeline, Dict[str, Any], Dict[str, float]]:
    """Train baseline Win Probability model using Logistic Regression."""
    X_train = train_df[feature_cols]
    y_train = train_df[TARGET_WIN].astype(int)

    X_test = test_df[feature_cols]
    y_test = test_df[TARGET_WIN].astype(int)

    if len(np.unique(y_train)) > 1:
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(class_weight="balanced", solver="lbfgs", max_iter=1000, random_state=42)),
        ])
    else:
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("classifier", DummyClassifier(strategy="most_frequent")),
        ])

    pipeline.fit(X_train, y_train)

    if hasattr(pipeline, "predict_proba") and len(pipeline.classes_) > 1:
        probs = pipeline.predict_proba(X_test)[:, 1]
    else:
        probs = np.ones(len(X_test)) if pipeline.classes_[0] == 1 else np.zeros(len(X_test))

    preds = (probs >= 0.5).astype(int)

    metrics = {
        "log_loss": float(log_loss(y_test, probs)) if len(np.unique(y_test)) > 1 else 0.0,
        "brier_score": float(brier_score_loss(y_test, probs)),
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probs)) if len(np.unique(y_test)) > 1 else None,
    }

    classifier = pipeline.named_steps["classifier"]
    coefs = dict(zip(feature_cols, classifier.coef_[0].tolist())) if hasattr(classifier, "coef_") and len(classifier.coef_) > 0 else {}

    return pipeline, metrics, coefs


def train_finish_position_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[Pipeline, Dict[str, Any], Dict[str, float]]:
    """Train Finish Position regression model using Random Forest Regressor."""
    train_clean = train_df.dropna(subset=[TARGET_FINISH_POSITION])
    test_clean = test_df.dropna(subset=[TARGET_FINISH_POSITION])

    X_train = train_clean[feature_cols]
    y_train = train_clean[TARGET_FINISH_POSITION].astype(float)

    X_test = test_clean[feature_cols]
    y_test = test_clean[TARGET_FINISH_POSITION].astype(float)

    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("regressor", RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)),
    ])

    pipeline.fit(X_train, y_train)
    preds = pipeline.predict(X_test)

    mae = float(mean_absolute_error(y_test, preds))
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))

    metrics = {
        "mae": mae,
        "rmse": rmse,
    }

    rf_model = pipeline.named_steps["regressor"]
    importances = dict(zip(feature_cols, rf_model.feature_importances_.tolist()))

    return pipeline, metrics, importances


def train_classification_model(
    target_name: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[Pipeline, Dict[str, Any], Dict[str, float]]:
    """Train secondary classification model (e.g. Podium or Top5) using Logistic Regression."""
    X_train = train_df[feature_cols]
    y_train = train_df[target_name].astype(int)

    X_test = test_df[feature_cols]
    y_test = test_df[target_name].astype(int)

    unique_classes = np.unique(y_train)
    if len(unique_classes) > 1:
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(class_weight="balanced", solver="lbfgs", max_iter=1000, random_state=42)),
        ])
    else:
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("classifier", DummyClassifier(strategy="most_frequent")),
        ])

    pipeline.fit(X_train, y_train)

    if len(pipeline.classes_) > 1 and hasattr(pipeline, "predict_proba"):
        probs = pipeline.predict_proba(X_test)[:, 1]
    else:
        probs = np.ones(len(X_test)) if pipeline.classes_[0] == 1 else np.zeros(len(X_test))

    preds = (probs >= 0.5).astype(int)

    metrics = {
        "log_loss": float(log_loss(y_test, probs)) if len(np.unique(y_test)) > 1 else 0.0,
        "brier_score": float(brier_score_loss(y_test, probs)),
        "accuracy": float(accuracy_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probs)) if len(np.unique(y_test)) > 1 else None,
    }

    classifier = pipeline.named_steps["classifier"]
    coefs = dict(zip(feature_cols, classifier.coef_[0].tolist())) if hasattr(classifier, "coef_") and len(classifier.coef_) > 0 else {}

    return pipeline, metrics, coefs


def compute_calibration_curves(
    win_model: Pipeline,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> Dict[str, Any]:
    """Compute calibration curve data for win probability model on test set."""
    X_test = test_df[feature_cols]
    y_test = test_df[TARGET_WIN].astype(int)

    if hasattr(win_model, "predict_proba") and len(win_model.classes_) > 1:
        probs = win_model.predict_proba(X_test)[:, 1]
    else:
        probs = np.zeros(len(X_test))

    if len(np.unique(y_test)) > 1:
        prob_true, prob_pred = calibration_curve(y_test, probs, n_bins=5, strategy="uniform")
        p_true_list = [float(p) for p in prob_true]
        p_pred_list = [float(p) for p in prob_pred]
    else:
        p_true_list = [float(np.mean(y_test))]
        p_pred_list = [float(np.mean(probs))]

    return {
        "target": TARGET_WIN,
        "n_bins": 5,
        "prob_true": p_true_list,
        "prob_pred": p_pred_list,
        "sample_size": len(y_test),
        "positive_class_ratio": float(np.mean(y_test)),
        "note": "Calibration curve computed on chronological test split. Small sample sizes per bin due to 5% win rate in 2025 single-season dataset.",
    }


def train_and_evaluate_all_models(
    df: pd.DataFrame,
    artifacts_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Orchestrate dataset validation, chronological split, training, evaluation, and artifact saving."""
    art_dir = artifacts_dir or ARTIFACTS_DIR
    models_dir = art_dir / "models"
    metrics_dir = art_dir / "metrics"
    calib_dir = art_dir / "calibration"
    meta_dir = art_dir / "metadata"

    for d in [models_dir, metrics_dir, calib_dir, meta_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. Leakage & Feature-Target Separation Validation
    is_valid, leakage_violations = validate_dataset_no_leakage(df)
    if not is_valid:
        raise ValueError(f"Dataset leakage check failed: {leakage_violations[0]}")

    feature_cols = get_feature_columns(df)
    logger.info("Validated %d feature columns: %s", len(feature_cols), feature_cols)

    # 2. Chronological Split
    train_df, val_df, test_df, split_summary = chronological_race_split(df, train_ratio=0.60, val_ratio=0.20)

    eval_test_df = test_df if not test_df.empty else val_df

    metrics_report: Dict[str, Any] = {}
    model_artifacts: Dict[str, Any] = {}
    explainability_report: Dict[str, Any] = {}

    # 3. Train Win Probability Model
    logger.info("Training Win Probability Model (Logistic Regression)...")
    win_model, win_metrics, win_coefs = train_win_probability_model(train_df, eval_test_df, feature_cols)
    metrics_report["win_probability_model"] = win_metrics
    explainability_report["win_probability_coefficients"] = win_coefs
    joblib.dump(win_model, models_dir / "win_probability_model.joblib")
    model_artifacts["win_probability_model"] = str((models_dir / "win_probability_model.joblib").resolve())

    # 4. Train Finish Position Model
    logger.info("Training Finish Position Model (Random Forest Regressor)...")
    finish_model, finish_metrics, finish_importances = train_finish_position_model(train_df, eval_test_df, feature_cols)
    metrics_report["finish_position_model"] = finish_metrics
    explainability_report["finish_position_importances"] = finish_importances
    joblib.dump(finish_model, models_dir / "finish_position_model.joblib")
    model_artifacts["finish_position_model"] = str((models_dir / "finish_position_model.joblib").resolve())

    # 5. Train Secondary Models (Podium & Top 5)
    logger.info("Training Podium Model (Logistic Regression)...")
    podium_model, podium_metrics, podium_coefs = train_classification_model(TARGET_PODIUM, train_df, eval_test_df, feature_cols)
    metrics_report["podium_model"] = podium_metrics
    explainability_report["podium_coefficients"] = podium_coefs
    joblib.dump(podium_model, models_dir / "podium_model.joblib")
    model_artifacts["podium_model"] = str((models_dir / "podium_model.joblib").resolve())

    logger.info("Training Top 5 Model (Logistic Regression)...")
    top5_model, top5_metrics, top5_coefs = train_classification_model(TARGET_TOP5, train_df, eval_test_df, feature_cols)
    metrics_report["top5_model"] = top5_metrics
    explainability_report["top5_coefficients"] = top5_coefs
    joblib.dump(top5_model, models_dir / "top5_model.joblib")
    model_artifacts["top5_model"] = str((models_dir / "top5_model.joblib").resolve())

    # 6. Compute Calibration Curves
    logger.info("Computing Calibration Curves...")
    calib_data = compute_calibration_curves(win_model, eval_test_df, feature_cols)
    with open(calib_dir / "calibration_data.json", "w") as f:
        json.dump(calib_data, f, indent=2)

    # 7. Save Metrics JSON
    with open(metrics_dir / "model_metrics.json", "w") as f:
        json.dump(metrics_report, f, indent=2)

    # 8. Save Metadata JSON files
    feature_meta = FEATURE_METADATA
    with open(meta_dir / "feature_metadata.json", "w") as f:
        json.dump({k: {**v, "first_available_stage": v["first_available_stage"].value if hasattr(v["first_available_stage"], "value") else str(v["first_available_stage"])} for k, v in feature_meta.items()}, f, indent=2)

    model_metadata = {
        "pipeline_version": "1.0.0",
        "split_summary": split_summary,
        "features_count": len(feature_cols),
        "features": feature_cols,
        "metrics": metrics_report,
        "explainability": explainability_report,
        "artifacts": model_artifacts,
    }
    with open(meta_dir / "model_metadata.json", "w") as f:
        json.dump(model_metadata, f, indent=2)

    logger.info("All models trained and evaluated successfully!")
    return model_metadata
