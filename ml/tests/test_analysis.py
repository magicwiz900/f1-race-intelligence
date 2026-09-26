import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from ml.stages import PredictionStage
from ml.training.analyze_predictions import (
    analyze_10bin_calibration,
    analyze_finish_position_model,
    analyze_race_probability_sums,
    analyze_stage_wise_performance,
    analyze_winner_probability_trajectories,
    run_full_prediction_analysis,
)


@pytest.fixture
def mock_trained_model():
    class DummyWinModel:
        classes_ = np.array([0, 1])

        def predict_proba(self, X):
            n = len(X)
            # Dummy probability based on row index or constant
            p = np.full((n, 2), 0.1)
            p[:, 1] = 0.2
            return p

    return DummyWinModel()


@pytest.fixture
def mock_regressor_model():
    class DummyFinishModel:
        def predict(self, X):
            n = len(X)
            return np.linspace(2.0, 18.0, n)

    return DummyFinishModel()


@pytest.fixture
def analysis_test_df():
    rows = []
    # 2 races, 4 drivers, 2 stages = 16 rows
    for r in range(20, 22):
        for d in range(1, 5):
            for stage in [PredictionStage.PRE_FP1.value, PredictionStage.POST_QUALIFYING.value]:
                rows.append({
                    "season": 2025,
                    "round": r,
                    "race_id": r,
                    "driver_id": d,
                    "driver_code": f"D{d}",
                    "team_id": 1 if d <= 2 else 2,
                    "prediction_stage": stage,
                    "driver_recent_avg_finish": float(d),
                    "driver_recent_win_rate": 1.0 if d == 1 else 0.0,
                    "driver_recent_podium_rate": 1.0 if d <= 3 else 0.0,
                    "driver_season_points": float(100 - d * 10),
                    "team_recent_avg_finish": 1.5 if d <= 2 else 3.5,
                    "team_recent_win_rate": 0.5,
                    "team_recent_podium_rate": 0.8,
                    "driver_circuit_avg_finish": float(d),
                    "driver_circuit_starts": 2,
                    "fp1_position": np.nan,
                    "fp1_lap_time": np.nan,
                    "fp1_gap_to_best": np.nan,
                    "fp2_position": np.nan,
                    "fp2_lap_time": np.nan,
                    "fp2_gap_to_best": np.nan,
                    "fp3_position": np.nan,
                    "fp3_lap_time": np.nan,
                    "fp3_gap_to_best": np.nan,
                    "fp_avg_position": np.nan,
                    "qualifying_position": np.nan,
                    "qualifying_lap_time": np.nan,
                    "qualifying_gap_to_pole": np.nan,
                    "race_finish_position": float(d),
                    "race_win": 1 if d == 1 else 0,
                    "race_podium": 1 if d <= 3 else 0,
                    "race_top5": 1 if d <= 4 else 0,
                })

    return pd.DataFrame(rows)


def test_analyze_stage_wise_performance(analysis_test_df, mock_trained_model):
    features = ["driver_recent_avg_finish", "driver_season_points"]
    stage_metrics = analyze_stage_wise_performance(analysis_test_df, mock_trained_model, features)

    assert "PRE_FP1" in stage_metrics
    assert "POST_QUALIFYING" in stage_metrics
    assert stage_metrics["PRE_FP1"]["samples"] == 8
    assert stage_metrics["PRE_FP1"]["mean_predicted_prob"] == pytest.approx(0.2)


def test_analyze_race_probability_sums(analysis_test_df, mock_trained_model):
    features = ["driver_recent_avg_finish", "driver_season_points"]
    sums_report = analyze_race_probability_sums(analysis_test_df, mock_trained_model, features)

    assert "mean_sum" in sums_report
    assert sums_report["mean_sum"] == pytest.approx(0.8) # 4 drivers * 0.2
    assert sums_report["sample_races_evaluated"] == 4 # 2 races * 2 stages


def test_analyze_10bin_calibration(analysis_test_df, mock_trained_model):
    features = ["driver_recent_avg_finish", "driver_season_points"]
    calib = analyze_10bin_calibration(analysis_test_df, mock_trained_model, features)

    assert "bins" in calib
    assert len(calib["bins"]) == 10
    # Bin 20-30% should contain all predictions (0.2 prob)
    bin_20_30 = calib["bins"][2]
    assert bin_20_30["count"] == len(analysis_test_df)


def test_analyze_winner_probability_trajectories(analysis_test_df, mock_trained_model):
    features = ["driver_recent_avg_finish", "driver_season_points"]
    trajectories = analyze_winner_probability_trajectories(analysis_test_df, mock_trained_model, features)

    assert len(trajectories) == 2 # 2 races
    t1 = trajectories[0]
    assert t1["winner_driver_code"] == "D1"
    assert t1["actual_finish_position"] == 1
    assert "PRE_FP1" in t1["stage_probabilities"]
    assert t1["stage_probabilities"]["PRE_FP1"] == pytest.approx(0.2)


def test_analyze_finish_position_model(analysis_test_df, mock_regressor_model):
    features = ["driver_recent_avg_finish", "driver_season_points"]
    pos_report = analyze_finish_position_model(analysis_test_df, mock_regressor_model, features)

    assert "mae" in pos_report
    assert pos_report["min_predicted_position"] >= 1.0
    assert pos_report["max_predicted_position"] <= 20.0
    assert pos_report["out_of_grid_bounds_count"] == 0
    assert pos_report["sanity_status"] == "VALID"


def test_full_analysis_pipeline_artifact_creation(analysis_test_df, tmp_path, monkeypatch):
    artifacts_dir = tmp_path / "artifacts"
    metrics_dir = artifacts_dir / "metrics"
    calib_dir = artifacts_dir / "calibration"
    models_dir = artifacts_dir / "models"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    calib_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    # Train dummy models to save joblib files
    from ml.training.trainer import train_and_evaluate_all_models
    train_and_evaluate_all_models(analysis_test_df, artifacts_dir=artifacts_dir)

    import ml.training.analyze_predictions as ap
    monkeypatch.setattr(ap, "ARTIFACTS_DIR", artifacts_dir)

    dataset_path = tmp_path / "f1_features_dataset.csv"
    analysis_test_df.to_csv(dataset_path, index=False)

    summary = run_full_prediction_analysis(dataset_path=dataset_path, output_dir=metrics_dir)

    assert (metrics_dir / "stage_metrics.json").exists()
    assert (metrics_dir / "winner_probability_trajectories.json").exists()
    assert (calib_dir / "calibration_10bin_data.json").exists()
    assert (metrics_dir / "prediction_sanity_report.json").exists()
