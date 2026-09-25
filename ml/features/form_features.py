from typing import Dict, Optional
import numpy as np
import pandas as pd

from ml.config import POINTS_MAP, ROLLING_WINDOW_RACES


def compute_driver_form_features(
    driver_id: int,
    target_season: int,
    target_round: int,
    historical_race_results_df: pd.DataFrame,
    window: int = ROLLING_WINDOW_RACES,
) -> Dict[str, Optional[float]]:
    """
    Compute rolling driver form features strictly using completed races prior to (target_season, target_round).
    historical_race_results_df must contain: ['season', 'round', 'driver_id', 'position'].
    """
    out = {
        "driver_recent_avg_finish": np.nan,
        "driver_recent_win_rate": np.nan,
        "driver_recent_podium_rate": np.nan,
        "driver_season_points": 0.0,
    }

    if historical_race_results_df.empty:
        return out

    # Filter prior races chronologically
    prior_mask = (
        (historical_race_results_df["season"] < target_season)
        | (
            (historical_race_results_df["season"] == target_season)
            & (historical_race_results_df["round"] < target_round)
        )
    )
    prior_df = historical_race_results_df[prior_mask]
    if prior_df.empty:
        return out

    driver_prior = prior_df[prior_df["driver_id"] == driver_id].sort_values(
        by=["season", "round"], ascending=True
    )

    # Season points before this race in current season
    current_season_df = driver_prior[driver_prior["season"] == target_season]
    season_points = 0.0
    for pos in current_season_df["position"].dropna():
        try:
            p_int = int(pos)
            season_points += POINTS_MAP.get(p_int, 0)
        except (ValueError, TypeError):
            pass

    out["driver_season_points"] = float(season_points)

    if driver_prior.empty:
        return out

    # Rolling window of last N races
    recent_races = driver_prior.tail(window)
    valid_positions = recent_races["position"].dropna()

    if not valid_positions.empty:
        positions = valid_positions.astype(float).values
        out["driver_recent_avg_finish"] = float(np.mean(positions))
        out["driver_recent_win_rate"] = float(np.mean(positions == 1.0))
        out["driver_recent_podium_rate"] = float(np.mean(positions <= 3.0))

    return out


def compute_team_form_features(
    team_id: Optional[int],
    target_season: int,
    target_round: int,
    historical_race_results_df: pd.DataFrame,
    window: int = ROLLING_WINDOW_RACES * 2,
) -> Dict[str, Optional[float]]:
    """
    Compute rolling team form features strictly using completed races prior to (target_season, target_round).
    historical_race_results_df must contain: ['season', 'round', 'team_id', 'position'].
    """
    out = {
        "team_recent_avg_finish": np.nan,
        "team_recent_win_rate": np.nan,
        "team_recent_podium_rate": np.nan,
    }

    if team_id is None or historical_race_results_df.empty:
        return out

    prior_mask = (
        (historical_race_results_df["season"] < target_season)
        | (
            (historical_race_results_df["season"] == target_season)
            & (historical_race_results_df["round"] < target_round)
        )
    )
    prior_df = historical_race_results_df[prior_mask]
    if prior_df.empty:
        return out

    team_prior = prior_df[prior_df["team_id"] == team_id].sort_values(
        by=["season", "round"], ascending=True
    )
    if team_prior.empty:
        return out

    recent_team_results = team_prior.tail(window)
    valid_positions = recent_team_results["position"].dropna()

    if not valid_positions.empty:
        positions = valid_positions.astype(float).values
        out["team_recent_avg_finish"] = float(np.mean(positions))
        out["team_recent_win_rate"] = float(np.mean(positions == 1.0))
        out["team_recent_podium_rate"] = float(np.mean(positions <= 3.0))

    return out
