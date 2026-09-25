from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest

from ml.data_split import chronological_race_split
from ml.training.trainer import train_and_evaluate_all_models
from ml.validation.leakage_checks import validate_feature_target_separation


@pytest.fixture
def dummy_training_df():
    """Create a small deterministic dataset DataFrame for testing model training mechanics."""
    rows = []
    # 5 races, 4 drivers, 2 stages = 40 rows
    for r in range(1, 6):
        for d in range(1, 5):
            for stage in ["PRE_FP1", "POST_QUALIFYING"]:
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
                    "fp1_position": np.nan if stage == "PRE_FP1" else float(d),
                    "fp1_lap_time": np.nan if stage == "PRE_FP1" else (80.0 + d),
                    "fp1_gap_to_best": np.nan if stage == "PRE_FP1" else float(d - 1),
                    "fp2_position": np.nan,
                    "fp2_lap_time": np.nan,
                    "fp2_gap_to_best": np.nan,
                    "fp3_position": np.nan,
                    "fp3_lap_time": np.nan,
                    "fp3_gap_to_best": np.nan,
                    "fp_avg_position": np.nan if stage == "PRE_FP1" else float(d),
                    "qualifying_position": np.nan if stage == "PRE_FP1" else float(d),
                    "qualifying_lap_time": np.nan if stage == "PRE_FP1" else (79.0 + d),
                    "qualifying_gap_to_pole": np.nan if stage == "PRE_FP1" else float(d - 1),
                    "race_finish_position": float(d),
                    "race_win": 1 if d == 1 else 0,
                    "race_podium": 1 if d <= 3 else 0,
                    "race_top5": 1 if d <= 4 else 0,
                })

    return pd.DataFrame(rows)


def test_feature_target_separation():
    # Valid features pass separation check
    valid_features = ["driver_recent_avg_finish", "driver_season_points", "fp1_gap_to_best"]
    assert validate_feature_target_separation(valid_features)

    # Including target column raises ValueError
    invalid_features = ["driver_recent_avg_finish", "race_win"]
    with pytest.raises(ValueError):
        validate_feature_target_separation(invalid_features)


def test_chronological_race_split(dummy_training_df):
    train_df, val_df, test_df, summary = chronological_race_split(dummy_training_df, train_ratio=0.6, val_ratio=0.2)

    assert not train_df.empty
    assert not test_df.empty

    # Ensure race boundary preservation (0 overlap)
    train_races = set(zip(train_df["season"], train_df["round"]))
    test_races = set(zip(test_df["season"], test_df["round"]))
    assert len(train_races.intersection(test_races)) == 0


def test_train_and_evaluate_all_models(dummy_training_df, tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    metadata = train_and_evaluate_all_models(dummy_training_df, artifacts_dir=artifacts_dir)

    assert "metrics" in metadata
    assert "win_probability_model" in metadata["metrics"]
    assert "finish_position_model" in metadata["metrics"]

    # Verify model artifact files exist and can be loaded
    win_model_path = artifacts_dir / "models" / "win_probability_model.joblib"
    assert win_model_path.exists()

    loaded_win_model = joblib.load(win_model_path)
    X_test = dummy_training_df[metadata["features"]]
    probs = loaded_win_model.predict_proba(X_test)[:, 1]

    # Verify probabilities are strictly bounded in [0, 1]
    assert np.all(probs >= 0.0)
    assert np.all(probs <= 1.0)

    # Verify metrics JSON exists
    assert (artifacts_dir / "metrics" / "model_metrics.json").exists()
    assert (artifacts_dir / "calibration" / "calibration_data.json").exists()
