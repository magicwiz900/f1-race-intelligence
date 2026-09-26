import numpy as np
import pandas as pd
import pytest

from ml.features.feature_pipeline import FeaturePipeline
from ml.stages import PredictionStage, is_stage_at_or_after


def test_stage_availability_helper():
    assert is_stage_at_or_after(PredictionStage.POST_FP1, PredictionStage.PRE_FP1) is True
    assert is_stage_at_or_after(PredictionStage.POST_FP1, PredictionStage.POST_FP1) is True
    assert is_stage_at_or_after(PredictionStage.POST_FP1, PredictionStage.POST_FP2) is False
    assert is_stage_at_or_after(PredictionStage.POST_FP3, PredictionStage.POST_QUALIFYING) is False
    assert is_stage_at_or_after(PredictionStage.POST_QUALIFYING, PredictionStage.POST_FP3) is True


def test_stage_aware_feature_masking():
    pipeline = FeaturePipeline()

    weekend_df = pd.DataFrame([
        {"session_type": "FP1", "driver_id": 1, "position": 2, "lap_time": 78.5},
        {"session_type": "FP2", "driver_id": 1, "position": 1, "lap_time": 77.9},
        {"session_type": "FP3", "driver_id": 1, "position": 3, "lap_time": 78.1},
        {"session_type": "QUALIFYING", "driver_id": 1, "position": 1, "lap_time": 76.8},
    ])

    historical_df = pd.DataFrame()

    # 1. PRE_FP1 stage masking
    pre_fp1_feats = pipeline.extract_features_for_row(
        driver_id=1,
        team_id=1,
        season=2025,
        round_num=1,
        circuit_name="Albert Park",
        stage=PredictionStage.PRE_FP1,
        current_weekend_results_df=weekend_df,
        historical_race_results_df=historical_df,
    )
    assert pd.isna(pre_fp1_feats["fp1_position"])
    assert pd.isna(pre_fp1_feats["fp2_position"])
    assert pd.isna(pre_fp1_feats["fp3_position"])
    assert pd.isna(pre_fp1_feats["qualifying_position"])

    # 2. POST_FP1 stage masking
    post_fp1_feats = pipeline.extract_features_for_row(
        driver_id=1,
        team_id=1,
        season=2025,
        round_num=1,
        circuit_name="Albert Park",
        stage=PredictionStage.POST_FP1,
        current_weekend_results_df=weekend_df,
        historical_race_results_df=historical_df,
    )
    assert post_fp1_feats["fp1_position"] == 2.0
    assert pd.isna(post_fp1_feats["fp2_position"])
    assert pd.isna(post_fp1_feats["fp3_position"])
    assert pd.isna(post_fp1_feats["qualifying_position"])

    # 3. POST_FP2 stage masking
    post_fp2_feats = pipeline.extract_features_for_row(
        driver_id=1,
        team_id=1,
        season=2025,
        round_num=1,
        circuit_name="Albert Park",
        stage=PredictionStage.POST_FP2,
        current_weekend_results_df=weekend_df,
        historical_race_results_df=historical_df,
    )
    assert post_fp2_feats["fp1_position"] == 2.0
    assert post_fp2_feats["fp2_position"] == 1.0
    assert pd.isna(post_fp2_feats["fp3_position"])
    assert pd.isna(post_fp2_feats["qualifying_position"])

    # 4. POST_FP3 stage masking
    post_fp3_feats = pipeline.extract_features_for_row(
        driver_id=1,
        team_id=1,
        season=2025,
        round_num=1,
        circuit_name="Albert Park",
        stage=PredictionStage.POST_FP3,
        current_weekend_results_df=weekend_df,
        historical_race_results_df=historical_df,
    )
    assert post_fp3_feats["fp1_position"] == 2.0
    assert post_fp3_feats["fp2_position"] == 1.0
    assert post_fp3_feats["fp3_position"] == 3.0
    assert pd.isna(post_fp3_feats["qualifying_position"])

    # 5. POST_QUALIFYING stage masking
    post_quali_feats = pipeline.extract_features_for_row(
        driver_id=1,
        team_id=1,
        season=2025,
        round_num=1,
        circuit_name="Albert Park",
        stage=PredictionStage.POST_QUALIFYING,
        current_weekend_results_df=weekend_df,
        historical_race_results_df=historical_df,
    )
    assert post_quali_feats["fp1_position"] == 2.0
    assert post_quali_feats["fp2_position"] == 1.0
    assert post_quali_feats["fp3_position"] == 3.0
    assert post_quali_feats["qualifying_position"] == 1.0
