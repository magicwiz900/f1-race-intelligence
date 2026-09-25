from typing import Dict, Optional
import numpy as np
import pandas as pd


def compute_circuit_history_features(
    driver_id: int,
    circuit_name: str,
    target_season: int,
    target_round: int,
    historical_race_results_df: pd.DataFrame,
) -> Dict[str, Optional[float]]:
    """
    Compute driver historical features at a specific circuit prior to (target_season, target_round).
    historical_race_results_df must contain: ['season', 'round', 'circuit', 'driver_id', 'position'].
    """
    out = {
        "driver_circuit_avg_finish": np.nan,
        "driver_circuit_starts": 0,
    }

    if historical_race_results_df.empty or not circuit_name:
        return out

    prior_mask = (
        (historical_race_results_df["circuit"] == circuit_name)
        & (
            (historical_race_results_df["season"] < target_season)
            | (
                (historical_race_results_df["season"] == target_season)
                & (historical_race_results_df["round"] < target_round)
            )
        )
    )
    circuit_prior = historical_race_results_df[prior_mask]
    if circuit_prior.empty:
        return out

    driver_circuit = circuit_prior[circuit_prior["driver_id"] == driver_id]
    if driver_circuit.empty:
        return out

    starts_count = len(driver_circuit)
    out["driver_circuit_starts"] = int(starts_count)

    valid_positions = driver_circuit["position"].dropna()
    if not valid_positions.empty:
        out["driver_circuit_avg_finish"] = float(np.mean(valid_positions.astype(float)))

    return out
