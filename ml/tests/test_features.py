import numpy as np
import pandas as pd
import pytest

from ml.features.circuit_features import compute_circuit_history_features
from ml.features.form_features import compute_driver_form_features, compute_team_form_features
from ml.features.pace_features import extract_session_pace_for_driver
from ml.features.qualifying_features import extract_qualifying_features_for_driver


def test_session_pace_features():
    df = pd.DataFrame([
        {"session_type": "FP1", "driver_id": 1, "position": 1, "lap_time": 90.0},
        {"session_type": "FP1", "driver_id": 2, "position": 2, "lap_time": 91.5},
    ])

    driver1_pace = extract_session_pace_for_driver(1, df, "FP1")
    assert driver1_pace["fp1_position"] == 1.0
    assert driver1_pace["fp1_lap_time"] == 90.0
    assert driver1_pace["fp1_gap_to_best"] == 0.0

    driver2_pace = extract_session_pace_for_driver(2, df, "FP1")
    assert driver2_pace["fp1_position"] == 2.0
    assert driver2_pace["fp1_lap_time"] == 91.5
    assert driver2_pace["fp1_gap_to_best"] == 1.5


def test_qualifying_features():
    df = pd.DataFrame([
        {"session_type": "QUALIFYING", "driver_id": 10, "position": 1, "lap_time": 80.0},
        {"session_type": "QUALIFYING", "driver_id": 20, "position": 2, "lap_time": 80.4},
    ])

    q_feats = extract_qualifying_features_for_driver(20, df)
    assert q_feats["qualifying_position"] == 2.0
    assert q_feats["qualifying_lap_time"] == 80.4
    assert q_feats["qualifying_gap_to_pole"] == pytest.approx(0.4)


def test_driver_and_team_form_features():
    history_df = pd.DataFrame([
        {"season": 2024, "round": 1, "driver_id": 100, "team_id": 5, "position": 1},
        {"season": 2024, "round": 2, "driver_id": 100, "team_id": 5, "position": 2},
        {"season": 2024, "round": 3, "driver_id": 100, "team_id": 5, "position": 3},
        {"season": 2025, "round": 1, "driver_id": 100, "team_id": 5, "position": 1}, # Target race is 2025 round 2
    ])

    # Driver form prior to 2025 round 2
    d_form = compute_driver_form_features(
        driver_id=100,
        target_season=2025,
        target_round=2,
        historical_race_results_df=history_df,
    )
    assert d_form["driver_recent_avg_finish"] == pytest.approx(1.75) # (1+2+3+1)/4
    assert d_form["driver_recent_win_rate"] == 0.5 # 2 wins out of 4
    assert d_form["driver_season_points"] == 25.0 # 2025 R1 win

    # Team form prior to 2025 round 2
    t_form = compute_team_form_features(
        team_id=5,
        target_season=2025,
        target_round=2,
        historical_race_results_df=history_df,
    )
    assert t_form["team_recent_avg_finish"] == pytest.approx(1.75)


def test_circuit_history_features():
    history_df = pd.DataFrame([
        {"season": 2023, "round": 1, "circuit": "Monaco", "driver_id": 1, "position": 1},
        {"season": 2024, "round": 1, "circuit": "Monaco", "driver_id": 1, "position": 2},
        {"season": 2024, "round": 5, "circuit": "Silverstone", "driver_id": 1, "position": 4},
    ])

    c_feats = compute_circuit_history_features(
        driver_id=1,
        circuit_name="Monaco",
        target_season=2025,
        target_round=8,
        historical_race_results_df=history_df,
    )
    assert c_feats["driver_circuit_starts"] == 2
    assert c_feats["driver_circuit_avg_finish"] == 1.5
