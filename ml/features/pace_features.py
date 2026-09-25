from typing import Dict, Optional
import numpy as np
import pandas as pd


def extract_session_pace_for_driver(
    driver_id: int,
    session_results_df: pd.DataFrame,
    session_type: str,
) -> Dict[str, Optional[float]]:
    """
    Extract position, best lap_time, and gap to session best lap_time for a driver in a practice session.
    session_results_df must contain: ['session_type', 'driver_id', 'position', 'lap_time'].
    """
    stype_upper = session_type.upper()
    prefix = stype_upper.lower()

    out_keys = {
        f"{prefix}_position": np.nan,
        f"{prefix}_lap_time": np.nan,
        f"{prefix}_gap_to_best": np.nan,
    }

    if session_results_df.empty:
        return out_keys

    sess_df = session_results_df[session_results_df["session_type"] == stype_upper]
    if sess_df.empty:
        return out_keys

    # Calculate session-best lap time
    valid_laps = sess_df["lap_time"].dropna()
    best_lap_in_session = valid_laps.min() if not valid_laps.empty else None

    # Driver row
    driver_row = sess_df[sess_df["driver_id"] == driver_id]
    if driver_row.empty:
        return out_keys

    row = driver_row.iloc[0]
    pos = float(row["position"]) if pd.notna(row.get("position")) else np.nan
    lap_t = float(row["lap_time"]) if pd.notna(row.get("lap_time")) else np.nan

    gap = np.nan
    if pd.notna(lap_t) and best_lap_in_session is not None and pd.notna(best_lap_in_session):
        gap = max(0.0, float(lap_t) - float(best_lap_in_session))

    return {
        f"{prefix}_position": pos,
        f"{prefix}_lap_time": lap_t,
        f"{prefix}_gap_to_best": gap,
    }
