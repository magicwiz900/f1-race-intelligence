from typing import Dict, Optional
import numpy as np
import pandas as pd


def extract_qualifying_features_for_driver(
    driver_id: int,
    session_results_df: pd.DataFrame,
) -> Dict[str, Optional[float]]:
    """
    Extract qualifying position, lap time, and gap to pole position for a driver.
    """
    out_keys = {
        "qualifying_position": np.nan,
        "qualifying_lap_time": np.nan,
        "qualifying_gap_to_pole": np.nan,
    }

    if session_results_df.empty:
        return out_keys

    quali_df = session_results_df[session_results_df["session_type"] == "QUALIFYING"]
    if quali_df.empty:
        return out_keys

    # Calculate pole position lap time
    valid_laps = quali_df["lap_time"].dropna()
    pole_time = valid_laps.min() if not valid_laps.empty else None

    driver_row = quali_df[quali_df["driver_id"] == driver_id]
    if driver_row.empty:
        return out_keys

    row = driver_row.iloc[0]
    pos = float(row["position"]) if pd.notna(row.get("position")) else np.nan
    lap_t = float(row["lap_time"]) if pd.notna(row.get("lap_time")) else np.nan

    gap = np.nan
    if pd.notna(lap_t) and pole_time is not None and pd.notna(pole_time):
        gap = max(0.0, float(lap_t) - float(pole_time))

    return {
        "qualifying_position": pos,
        "qualifying_lap_time": lap_t,
        "qualifying_gap_to_pole": gap,
    }
