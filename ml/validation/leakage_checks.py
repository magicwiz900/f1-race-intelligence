import logging
from typing import Dict, List, Tuple
import pandas as pd

from ml.config import TARGET_COLUMNS
from ml.features.metadata import FEATURE_METADATA
from ml.stages import PredictionStage, is_stage_at_or_after

logger = logging.getLogger(__name__)


def validate_feature_target_separation(feature_names: List[str]) -> bool:
    """
    Verify that no target columns appear in the feature column list X.
    Raises ValueError if a target column is detected in feature list.
    """
    leakage_detected = []
    for feat in feature_names:
        if feat in TARGET_COLUMNS:
            leakage_detected.append(feat)
        elif "finish_position" in feat and feat != "driver_recent_avg_finish" and feat != "team_recent_avg_finish" and feat != "driver_circuit_avg_finish":
            leakage_detected.append(feat)
        elif feat in ["race_win", "race_podium", "race_top5", "position"]:
            leakage_detected.append(feat)

    if leakage_detected:
        msg = f"Target Leakage Detected! Target columns found in feature matrix X: {leakage_detected}"
        logger.error(msg)
        raise ValueError(msg)

    return True


def verify_row_stage_compliance(row: pd.Series) -> List[str]:
    """
    Verify a single DataFrame row against stage availability rules.
    Returns a list of violation messages if future data leakage is detected.
    """
    stage_str = row.get("prediction_stage")
    if not stage_str:
        return ["Missing prediction_stage field in row."]

    try:
        stage = PredictionStage(stage_str)
    except ValueError:
        return [f"Unknown prediction_stage: {stage_str}"]

    violations = []

    # Stage metadata compliance check
    for feat_name, meta in FEATURE_METADATA.items():
        first_avail = meta.get("first_available_stage")
        if first_avail and not is_stage_at_or_after(stage, first_avail):
            val = row.get(feat_name)
            if pd.notna(val):
                violations.append(
                    f"Leakage Violation: Feature '{feat_name}' (requires {first_avail.value}) "
                    f"has non-null value {val} at stage {stage.value}."
                )

    return violations


def validate_dataset_no_leakage(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    Validate an entire engineered dataset DataFrame for data leakage.
    Returns (is_valid, list_of_violations).
    """
    all_violations = []

    if df.empty:
        return True, []

    # Ensure no target columns are listed as input features in metadata
    for target_col in TARGET_COLUMNS:
        if target_col in FEATURE_METADATA:
            all_violations.append(f"Critical Metadata Bug: Target '{target_col}' is registered in FEATURE_METADATA!")

    # Check each row in DataFrame
    for idx, row in df.iterrows():
        row_violations = verify_row_stage_compliance(row)
        if row_violations:
            for v in row_violations:
                all_violations.append(f"Row {idx} (Race {row.get('race_id')}, Driver {row.get('driver_code')}, Stage {row.get('prediction_stage')}): {v}")

    is_valid = len(all_violations) == 0
    if not is_valid:
        logger.error("Data Leakage Validation Failed with %d violations!", len(all_violations))
    else:
        logger.info("Data Leakage Validation Passed cleanly!")

    return is_valid, all_violations
