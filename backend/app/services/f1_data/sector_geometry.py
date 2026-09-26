import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from app.services.f1_data.fastf1_service import FastF1Service

logger = logging.getLogger(__name__)


class SectorGeometryError(Exception):
    """Base exception for sector geometry extraction errors."""
    pass


class SectorGeometryUnavailableError(SectorGeometryError):
    """Raised when telemetry or lap sector data is unavailable for sector geometry."""
    pass


def _to_seconds(val: Any) -> Optional[float]:
    """Convert a timedelta, pd.Timedelta, float, or integer value to seconds."""
    if val is None or pd.isna(val):
        return None
    if hasattr(val, "total_seconds"):
        return float(val.total_seconds())
    try:
        f = float(val)
        return f if np.isfinite(f) else None
    except (ValueError, TypeError):
        return None


class SectorGeometryService:
    """Service for extracting and normalizing circuit sector geometry (S1/S2/S3) from FastF1 telemetry."""

    # Priority list of session types to search for telemetry: (FastF1 code, display name)
    SESSION_PRIORITIES: List[Tuple[str, str]] = [
        ("Q", "QUALIFYING"),
        ("FP3", "FP3"),
        ("FP2", "FP2"),
        ("FP1", "FP1"),
        ("R", "RACE"),
    ]

    _cache: Dict[int, Dict[str, Any]] = {}

    def __init__(self, fastf1_service: Optional[FastF1Service] = None):
        self.fastf1_service = fastf1_service or FastF1Service()

    @classmethod
    def clear_cache(cls) -> None:
        """Clear in-memory sector geometry cache."""
        cls._cache.clear()

    def get_sector_geometry(
        self,
        race_id: int,
        season: int,
        round_num: int,
        race_name: str,
        circuit: str,
    ) -> Dict[str, Any]:
        """
        Retrieve normalized sector geometry for a given race.
        Checks in-memory cache first before extracting from FastF1.
        """
        if race_id in self._cache:
            logger.info("Returning cached sector geometry for race_id %d", race_id)
            return self._cache[race_id]

        session_used, total_distance, sectors = self._extract_raw_sector_geometry(season, round_num)

        geometry_data = {
            "race_id": race_id,
            "season": season,
            "race_name": race_name,
            "circuit": circuit,
            "source": "FastF1 telemetry",
            "session_type": session_used,
            "coordinate_system": "normalized",
            "total_distance": round(total_distance, 1),
            "sectors": sectors,
        }

        self._cache[race_id] = geometry_data
        return geometry_data

    def _extract_raw_sector_geometry(
        self, season: int, round_num: int
    ) -> Tuple[str, float, List[Dict[str, Any]]]:
        """
        Attempt to load telemetry from sessions in priority order and extract S1/S2/S3 sector geometry.
        """
        if not self.fastf1_service.is_available():
            raise SectorGeometryUnavailableError("FastF1 library is not installed or available.")

        last_error = None
        for session_code, display_name in self.SESSION_PRIORITIES:
            try:
                logger.info(
                    "Attempting to load sector geometry from %s (%s) for season %d round %d",
                    display_name, session_code, season, round_num
                )

                session = self.fastf1_service.get_session(
                    year=season,
                    grand_prix=round_num,
                    session_type=session_code,
                )

                # Load lap timing and telemetry data
                self.fastf1_service.load_session(session, laps=True, telemetry=True, weather=False)

                result = self._extract_sector_telemetry(session)
                if result is not None:
                    total_distance, sectors = result
                    logger.info("Successfully extracted sector geometry from %s session", display_name)
                    return display_name, total_distance, sectors

            except Exception as e:
                logger.warning("Failed extracting sector telemetry from %s session: %s", display_name, e)
                last_error = e

        raise SectorGeometryUnavailableError(
            f"No usable sector geometry telemetry found for season {season} round {round_num}. Details: {last_error}"
        )

    def _extract_sector_telemetry(self, session: Any) -> Optional[Tuple[float, List[Dict[str, Any]]]]:
        """Extract S1/S2/S3 telemetry points and boundaries from a representative lap."""
        if not hasattr(session, "laps") or session.laps is None or session.laps.empty:
            return None

        candidate_laps = []

        # 1. Try fastest lap first
        try:
            fastest_lap = session.laps.pick_fastest()
            if fastest_lap is not None and getattr(fastest_lap, "empty", None) is not True:
                candidate_laps.append(fastest_lap)
        except Exception as e:
            logger.debug("pick_fastest failed: %s", e)

        # 2. Try quick laps
        try:
            if hasattr(session.laps, "pick_quicklaps"):
                quick_laps = session.laps.pick_quicklaps()
                if quick_laps is not None and getattr(quick_laps, "empty", None) is not True:
                    for _, lap in quick_laps.iterrows():
                        candidate_laps.append(lap)
        except Exception as e:
            logger.debug("pick_quicklaps failed: %s", e)

        # 3. Fallback: iterate over all laps sorted by LapTime
        try:
            if "LapTime" in session.laps.columns:
                valid_laps = session.laps[session.laps["LapTime"].notna()]
                sorted_laps = valid_laps.sort_values(by="LapTime")
                for _, lap in sorted_laps.iterrows():
                    candidate_laps.append(lap)
        except Exception as e:
            logger.debug("Fallback lap iteration failed: %s", e)

        for lap in candidate_laps:
            try:
                # Check sector times
                s1_val = lap.get("Sector1Time") if hasattr(lap, "get") else (lap["Sector1Time"] if "Sector1Time" in lap else None)
                s2_val = lap.get("Sector2Time") if hasattr(lap, "get") else (lap["Sector2Time"] if "Sector2Time" in lap else None)
                s3_val = lap.get("Sector3Time") if hasattr(lap, "get") else (lap["Sector3Time"] if "Sector3Time" in lap else None)

                s1_sec = _to_seconds(s1_val)
                s2_sec = _to_seconds(s2_val)
                s3_sec = _to_seconds(s3_val)

                if s1_sec is None or s2_sec is None or s3_sec is None or s1_sec <= 0 or s2_sec <= 0 or s3_sec <= 0:
                    continue

                t1 = s1_sec
                t2 = s1_sec + s2_sec
                t3 = s1_sec + s2_sec + s3_sec

                tel = None
                if hasattr(lap, "get_telemetry") and callable(lap.get_telemetry):
                    tel = lap.get_telemetry()
                elif isinstance(lap, pd.Series) and "get_telemetry" in lap and callable(lap["get_telemetry"]):
                    tel = lap["get_telemetry"]()

                if tel is None or (hasattr(tel, "empty") and tel.empty):
                    continue

                if "X" not in tel.columns or "Y" not in tel.columns:
                    continue

                df_valid = tel.dropna(subset=["X", "Y"]).copy()
                x_num = pd.to_numeric(df_valid["X"], errors="coerce")
                y_num = pd.to_numeric(df_valid["Y"], errors="coerce")
                valid_mask = np.isfinite(x_num) & np.isfinite(y_num)
                df_valid = df_valid[valid_mask].copy()

                if len(df_valid) < 5:
                    continue

                # Ensure Distance column exists
                if hasattr(df_valid, "add_distance"):
                    df_valid = df_valid.add_distance()
                elif "Distance" not in df_valid.columns or df_valid["Distance"].dropna().empty:
                    dx = df_valid["X"].astype(float).diff().fillna(0)
                    dy = df_valid["Y"].astype(float).diff().fillna(0)
                    df_valid["Distance"] = np.sqrt(dx**2 + dy**2).cumsum()

                if "Distance" not in df_valid.columns:
                    continue

                # Ensure TimeSec column exists for time-based interpolation
                if "Time" in df_valid.columns:
                    df_valid["TimeSec"] = df_valid["Time"].apply(_to_seconds)
                elif "SessionTime" in df_valid.columns:
                    lap_start = lap.get("LapStartTime") if hasattr(lap, "get") else (lap["LapStartTime"] if "LapStartTime" in lap else None)
                    lap_start_sec = _to_seconds(lap_start) or 0.0
                    df_valid["TimeSec"] = df_valid["SessionTime"].apply(_to_seconds) - lap_start_sec
                else:
                    # Fallback: estimate TimeSec based on distance ratio if no time column exists
                    max_d = df_valid["Distance"].max()
                    if max_d > 0:
                        df_valid["TimeSec"] = (df_valid["Distance"] / max_d) * t3
                    else:
                        continue

                df_valid = df_valid.dropna(subset=["Distance", "TimeSec"]).copy()
                if len(df_valid) < 5:
                    continue

                distances = df_valid["Distance"].astype(float).values
                times = df_valid["TimeSec"].astype(float).values
                x_coords = df_valid["X"].astype(float).values
                y_coords = df_valid["Y"].astype(float).values

                max_dist = distances[-1]
                if max_dist <= 0:
                    continue

                # Interpolate distances at sector timing boundaries t1 and t2
                dist_s1 = float(np.interp(t1, times, distances))
                dist_s2 = float(np.interp(t2, times, distances))
                dist_s3 = float(max_dist)

                if not (0 < dist_s1 < dist_s2 <= dist_s3):
                    continue

                # Interpolate exact X/Y points at sector boundary distances
                x_s1 = float(np.interp(dist_s1, distances, x_coords))
                y_s1 = float(np.interp(dist_s1, distances, y_coords))

                x_s2 = float(np.interp(dist_s2, distances, x_coords))
                y_s2 = float(np.interp(dist_s2, distances, y_coords))

                # Partition telemetry path into 3 sectors
                s1_raw: List[Tuple[float, float]] = []
                s2_raw: List[Tuple[float, float]] = []
                s3_raw: List[Tuple[float, float]] = []

                for i in range(len(distances)):
                    d = distances[i]
                    pt = (x_coords[i], y_coords[i])
                    if d < dist_s1:
                        s1_raw.append(pt)
                    elif d < dist_s2:
                        if not s2_raw:
                            s1_raw.append((x_s1, y_s1))
                            s2_raw.append((x_s1, y_s1))
                        s2_raw.append(pt)
                    else:
                        if not s3_raw:
                            s2_raw.append((x_s2, y_s2))
                            s3_raw.append((x_s2, y_s2))
                        s3_raw.append(pt)

                # Ensure boundaries close cleanly if loop finished in s2
                if not s2_raw and s1_raw:
                    s2_raw.append((x_s1, y_s1))
                    s2_raw.append((x_s2, y_s2))
                if not s3_raw and s2_raw:
                    s3_raw.append((x_s2, y_s2))
                    s3_raw.append((x_coords[-1], y_coords[-1]))

                if not s1_raw or not s2_raw or not s3_raw:
                    continue

                # Compute overall normalization parameters across all points
                all_pts = list(zip(x_coords, y_coords)) + [(x_s1, y_s1), (x_s2, y_s2)]
                x_vals = [p[0] for p in all_pts]
                y_vals = [p[1] for p in all_pts]
                x_min, x_max = min(x_vals), max(x_vals)
                y_min, y_max = min(y_vals), max(y_vals)
                scale = max(x_max - x_min, y_max - y_min)
                if scale == 0:
                    scale = 1.0

                def norm_pts(pts: List[Tuple[float, float]]) -> List[Dict[str, float]]:
                    return [
                        {
                            "x": round((px - x_min) / scale, 5),
                            "y": round((y_max - py) / scale, 5),
                        }
                        for px, py in pts
                    ]

                s1_points = norm_pts(s1_raw)
                s2_points = norm_pts(s2_raw)
                s3_points = norm_pts(s3_raw)

                sectors = [
                    {
                        "sector": 1,
                        "start_distance": 0.0,
                        "end_distance": round(dist_s1, 1),
                        "start_relative_distance": 0.0,
                        "end_relative_distance": round(dist_s1 / dist_s3, 3),
                        "points": s1_points,
                    },
                    {
                        "sector": 2,
                        "start_distance": round(dist_s1, 1),
                        "end_distance": round(dist_s2, 1),
                        "start_relative_distance": round(dist_s1 / dist_s3, 3),
                        "end_relative_distance": round(dist_s2 / dist_s3, 3),
                        "points": s2_points,
                    },
                    {
                        "sector": 3,
                        "start_distance": round(dist_s2, 1),
                        "end_distance": round(dist_s3, 1),
                        "start_relative_distance": round(dist_s2 / dist_s3, 3),
                        "end_relative_distance": 1.0,
                        "points": s3_points,
                    },
                ]

                return dist_s3, sectors

            except Exception as e:
                logger.debug("Failed getting sector telemetry for candidate lap: %s", e)
                continue

        return None
