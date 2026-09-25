import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from ml.features.circuit_features import compute_circuit_history_features
from ml.features.form_features import compute_driver_form_features, compute_team_form_features
from ml.features.metadata import FEATURE_METADATA
from ml.features.pace_features import extract_session_pace_for_driver
from ml.features.qualifying_features import extract_qualifying_features_for_driver
from ml.stages import PredictionStage, is_stage_at_or_after

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """Orchestrates stage-aware feature extraction with strict leakage protection."""

    def __init__(self):
        self.metadata = FEATURE_METADATA

    def extract_features_for_row(
        self,
        driver_id: int,
        team_id: Optional[int],
        season: int,
        round_num: int,
        circuit_name: str,
        stage: PredictionStage,
        current_weekend_results_df: pd.DataFrame,
        historical_race_results_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Extract all features for a single (driver, race, stage) tuple.
        Masks any feature that belongs to a session occurring AFTER the specified stage.
        """
        feature_dict: Dict[str, Any] = {}

        # 1. Historical Driver & Team Form
        driver_form = compute_driver_form_features(
            driver_id=driver_id,
            target_season=season,
            target_round=round_num,
            historical_race_results_df=historical_race_results_df,
        )
        feature_dict.update(driver_form)

        team_form = compute_team_form_features(
            team_id=team_id,
            target_season=season,
            target_round=round_num,
            historical_race_results_df=historical_race_results_df,
        )
        feature_dict.update(team_form)

        # 2. Circuit History
        circuit_hist = compute_circuit_history_features(
            driver_id=driver_id,
            circuit_name=circuit_name,
            target_season=season,
            target_round=round_num,
            historical_race_results_df=historical_race_results_df,
        )
        feature_dict.update(circuit_hist)

        # 3. Practice Session Pace Features (FP1, FP2, FP3)
        fp1_pace = extract_session_pace_for_driver(driver_id, current_weekend_results_df, "FP1")
        fp2_pace = extract_session_pace_for_driver(driver_id, current_weekend_results_df, "FP2")
        fp3_pace = extract_session_pace_for_driver(driver_id, current_weekend_results_df, "FP3")

        feature_dict.update(fp1_pace)
        feature_dict.update(fp2_pace)
        feature_dict.update(fp3_pace)

        # 4. Session Consistency (Mean practice position up to stage)
        fp_positions = []
        if is_stage_at_or_after(stage, PredictionStage.POST_FP1) and pd.notna(fp1_pace["fp1_position"]):
            fp_positions.append(fp1_pace["fp1_position"])
        if is_stage_at_or_after(stage, PredictionStage.POST_FP2) and pd.notna(fp2_pace["fp2_position"]):
            fp_positions.append(fp2_pace["fp2_position"])
        if is_stage_at_or_after(stage, PredictionStage.POST_FP3) and pd.notna(fp3_pace["fp3_position"]):
            fp_positions.append(fp3_pace["fp3_position"])

        feature_dict["fp_avg_position"] = float(np.mean(fp_positions)) if fp_positions else np.nan

        # 5. Qualifying Features
        qualifying_feats = extract_qualifying_features_for_driver(driver_id, current_weekend_results_df)
        feature_dict.update(qualifying_feats)

        # 6. ENFORCE STAGE AVAILABILITY MASKING
        # Set features to np.nan if their required stage is chronologically AFTER current stage
        for feat_name, meta in self.metadata.items():
            first_avail = meta.get("first_available_stage")
            if first_avail and not is_stage_at_or_after(stage, first_avail):
                feature_dict[feat_name] = np.nan

        return feature_dict
