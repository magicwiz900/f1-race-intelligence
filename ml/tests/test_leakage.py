import numpy as np
import pandas as pd

from ml.features.feature_pipeline import FeaturePipeline
from ml.stages import PredictionStage
from ml.validation.leakage_checks import validate_dataset_no_leakage, verify_row_stage_compliance


def test_stage_availability_masking():
    pipeline = FeaturePipeline()

    weekend_df = pd.DataFrame([
        {"session_type": "FP1", "driver_id": 1, "position": 1, "lap_time": 90.0},
        {"session_type": "FP2", "driver_id": 1, "position": 2, "lap_time": 89.5},
        {"session_type": "FP3", "driver_id": 1, "position": 3, "lap_time": 89.0},
        {"session_type": "QUALIFYING", "driver_id": 1, "position": 1, "lap_time": 88.0},
    ])
    history_df = pd.DataFrame()

    # Stage PRE_FP1: All session features must be masked (NaN)
    pre_fp1_feats = pipeline.extract_features_for_row(
        driver_id=1,
        team_id=1,
        season=2025,
        round_num=1,
        circuit_name="Albert Park",
        stage=PredictionStage.PRE_FP1,
        current_weekend_results_df=weekend_df,
        historical_race_results_df=history_df,
    )

    assert np.isnan(pre_fp1_feats["fp1_position"])
    assert np.isnan(pre_fp1_feats["fp2_position"])
    assert np.isnan(pre_fp1_feats["fp3_position"])
    assert np.isnan(pre_fp1_feats["qualifying_position"])

    # Stage POST_FP1: Only FP1 features populated, FP2/FP3/Qualifying masked
    post_fp1_feats = pipeline.extract_features_for_row(
        driver_id=1,
        team_id=1,
        season=2025,
        round_num=1,
        circuit_name="Albert Park",
        stage=PredictionStage.POST_FP1,
        current_weekend_results_df=weekend_df,
        historical_race_results_df=history_df,
    )
    assert post_fp1_feats["fp1_position"] == 1.0
    assert np.isnan(post_fp1_feats["fp2_position"])
    assert np.isnan(post_fp1_feats["fp3_position"])
    assert np.isnan(post_fp1_feats["qualifying_position"])

    # Stage POST_QUALIFYING: FP1, FP2, FP3, and Qualifying populated
    post_q_feats = pipeline.extract_features_for_row(
        driver_id=1,
        team_id=1,
        season=2025,
        round_num=1,
        circuit_name="Albert Park",
        stage=PredictionStage.POST_QUALIFYING,
        current_weekend_results_df=weekend_df,
        historical_race_results_df=history_df,
    )
    assert post_q_feats["fp1_position"] == 1.0
    assert post_q_feats["fp2_position"] == 2.0
    assert post_q_feats["fp3_position"] == 3.0
    assert post_q_feats["qualifying_position"] == 1.0


def test_leakage_validator_detects_violations():
    # Valid PRE_FP1 row
    valid_row = pd.Series({
        "prediction_stage": "PRE_FP1",
        "driver_recent_avg_finish": 2.5,
        "fp1_position": np.nan,
        "qualifying_position": np.nan,
    })
    assert len(verify_row_stage_compliance(valid_row)) == 0

    # Invalid PRE_FP1 row with leaked qualifying position
    leaked_row = pd.Series({
        "prediction_stage": "PRE_FP1",
        "driver_recent_avg_finish": 2.5,
        "qualifying_position": 1.0, # LEAK!
    })
    violations = verify_row_stage_compliance(leaked_row)
    assert len(violations) > 0
    assert "qualifying_position" in violations[0]
