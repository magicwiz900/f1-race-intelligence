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
    team_form_fallback: Optional[Dict[str, Optional[float]]] = None,
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

    if not historical_race_results_df.empty:
        # Filter prior races chronologically
        prior_mask = (
            (historical_race_results_df["season"] < target_season)
            | (
                (historical_race_results_df["season"] == target_season)
                & (historical_race_results_df["round"] < target_round)
            )
        )
        prior_df = historical_race_results_df[prior_mask]
        if not prior_df.empty:
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

            if not driver_prior.empty:
                # Rolling window of last N races
                recent_races = driver_prior.tail(window)
                valid_positions = recent_races["position"].dropna()

                if not valid_positions.empty:
                    positions = valid_positions.astype(float).values
                    out["driver_recent_avg_finish"] = float(np.mean(positions))
                    out["driver_recent_win_rate"] = float(np.mean(positions == 1.0))
                    out["driver_recent_podium_rate"] = float(np.mean(positions <= 3.0))

    # Deterministic fallback to team-level historical form if driver has no prior personal history
    if team_form_fallback:
        if (
            pd.isna(out["driver_recent_avg_finish"])
            and team_form_fallback.get("team_recent_avg_finish") is not None
            and pd.notna(team_form_fallback.get("team_recent_avg_finish"))
        ):
            out["driver_recent_avg_finish"] = float(team_form_fallback["team_recent_avg_finish"])
        if (
            pd.isna(out["driver_recent_win_rate"])
            and team_form_fallback.get("team_recent_win_rate") is not None
            and pd.notna(team_form_fallback.get("team_recent_win_rate"))
        ):
            out["driver_recent_win_rate"] = float(team_form_fallback["team_recent_win_rate"])
        if (
            pd.isna(out["driver_recent_podium_rate"])
            and team_form_fallback.get("team_recent_podium_rate") is not None
            and pd.notna(team_form_fallback.get("team_recent_podium_rate"))
        ):
            out["driver_recent_podium_rate"] = float(team_form_fallback["team_recent_podium_rate"])

    return out


DEFAULT_TEAM_FORM_BASELINES = {
    8: {"team_recent_avg_finish": 4.0, "team_recent_win_rate": 0.35, "team_recent_podium_rate": 0.65},   # Red Bull
    3: {"team_recent_avg_finish": 4.5, "team_recent_win_rate": 0.20, "team_recent_podium_rate": 0.50},   # Ferrari
    5: {"team_recent_avg_finish": 5.0, "team_recent_win_rate": 0.20, "team_recent_podium_rate": 0.50},   # McLaren
    6: {"team_recent_avg_finish": 5.5, "team_recent_win_rate": 0.10, "team_recent_podium_rate": 0.40},   # Mercedes
    2: {"team_recent_avg_finish": 8.5, "team_recent_win_rate": 0.00, "team_recent_podium_rate": 0.15},   # Aston Martin
    1: {"team_recent_avg_finish": 11.0, "team_recent_win_rate": 0.00, "team_recent_podium_rate": 0.05},  # Alpine
    7: {"team_recent_avg_finish": 11.5, "team_recent_win_rate": 0.00, "team_recent_podium_rate": 0.00},  # RB
    4: {"team_recent_avg_finish": 12.0, "team_recent_win_rate": 0.00, "team_recent_podium_rate": 0.00},  # Haas
    10: {"team_recent_avg_finish": 13.5, "team_recent_win_rate": 0.00, "team_recent_podium_rate": 0.00}, # Williams
    9: {"team_recent_avg_finish": 14.5, "team_recent_win_rate": 0.00, "team_recent_podium_rate": 0.00},  # Sauber
}


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

    def _apply_fallback():
        if team_id is not None and team_id in DEFAULT_TEAM_FORM_BASELINES:
            return dict(DEFAULT_TEAM_FORM_BASELINES[team_id])
        elif team_id is not None:
            return {
                "team_recent_avg_finish": 10.5,
                "team_recent_win_rate": 0.0,
                "team_recent_podium_rate": 0.10,
            }
        return out

    if team_id is None:
        return out

    if historical_race_results_df.empty:
        return _apply_fallback()

    prior_mask = (
        (historical_race_results_df["season"] < target_season)
        | (
            (historical_race_results_df["season"] == target_season)
            & (historical_race_results_df["round"] < target_round)
        )
    )
    prior_df = historical_race_results_df[prior_mask]
    if prior_df.empty:
        return _apply_fallback()

    team_prior = prior_df[prior_df["team_id"] == team_id].sort_values(
        by=["season", "round"], ascending=True
    )
    if team_prior.empty:
        return _apply_fallback()

    recent_team_results = team_prior.tail(window)
    valid_positions = recent_team_results["position"].dropna()

    if not valid_positions.empty:
        positions = valid_positions.astype(float).values
        out["team_recent_avg_finish"] = float(np.mean(positions))
        out["team_recent_win_rate"] = float(np.mean(positions == 1.0))
        out["team_recent_podium_rate"] = float(np.mean(positions <= 3.0))
    else:
        return _apply_fallback()

    return out

