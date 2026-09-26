import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from app.services.f1_data.fastf1_service import FastF1Service

logger = logging.getLogger(__name__)


class TrackGeometryError(Exception):
    """Base exception for track geometry extraction errors."""
    pass


class TrackGeometryUnavailableError(TrackGeometryError):
    """Raised when telemetry or lap data is unavailable for track geometry."""
    pass


class TrackGeometryService:
    """Service for extracting and normalizing circuit track geometry from FastF1 telemetry."""

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
        """Clear in-memory geometry cache."""
        cls._cache.clear()

    def get_track_geometry(
        self,
        race_id: int,
        season: int,
        round_num: int,
        race_name: str,
        circuit: str,
    ) -> Dict[str, Any]:
        """
        Retrieve normalized track geometry for a given race.
        Checks in-memory cache first before extracting from FastF1.
        """
        if race_id in self._cache:
            logger.info("Returning cached track geometry for race_id %d", race_id)
            return self._cache[race_id]

        session_used, raw_points = self._extract_raw_geometry(season, round_num)
        normalized_points = self._normalize_coordinates(raw_points)

        geometry_data = {
            "race_id": race_id,
            "season": season,
            "race_name": race_name,
            "circuit": circuit,
            "source": "FastF1 telemetry",
            "session_type": session_used,
            "coordinate_system": "normalized",
            "point_count": len(normalized_points),
            "points": normalized_points,
        }

        self._cache[race_id] = geometry_data
        return geometry_data

    def _extract_raw_geometry(self, season: int, round_num: int) -> Tuple[str, List[Tuple[float, float]]]:
        """
        Attempt to load telemetry from sessions in priority order and extract X/Y coordinates
        from a representative valid lap.
        """
        if not self.fastf1_service.is_available():
            raise TrackGeometryUnavailableError("FastF1 library is not installed or available.")

        last_error = None
        for session_code, display_name in self.SESSION_PRIORITIES:
            try:
                logger.info(
                    "Attempting to load track geometry from %s (%s) for season %d round %d",
                    display_name, session_code, season, round_num
                )

                session = self.fastf1_service.get_session(
                    year=season,
                    grand_prix=round_num,
                    session_type=session_code,
                )

                # Load lap timing and telemetry data
                self.fastf1_service.load_session(session, laps=True, telemetry=True, weather=False)

                points = self._extract_lap_telemetry(session)
                if points and len(points) >= 5:
                    logger.info("Successfully extracted %d geometry points from %s session", len(points), display_name)
                    return display_name, points

            except Exception as e:
                logger.warning("Failed extracting telemetry from %s session: %s", display_name, e)
                last_error = e

        raise TrackGeometryUnavailableError(
            f"No usable track geometry telemetry found for season {season} round {round_num}. Details: {last_error}"
        )

    def _extract_lap_telemetry(self, session: Any) -> Optional[List[Tuple[float, float]]]:
        """Extract valid X/Y telemetry coordinates from a representative lap in the session."""
        if not hasattr(session, "laps") or session.laps is None or session.laps.empty:
            return None

        # Build list of candidate laps to inspect
        candidate_laps = []

        # 1. Try fastest lap first
        try:
            fastest_lap = session.laps.pick_fastest()
            if fastest_lap is not None:
                is_empty = getattr(fastest_lap, "empty", None)
                if is_empty is not True:
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

        # Iterate candidate laps until usable telemetry is extracted
        for lap in candidate_laps:
            try:
                tel = None
                if hasattr(lap, "get_telemetry") and callable(lap.get_telemetry):
                    tel = lap.get_telemetry()
                elif isinstance(lap, pd.Series) and "get_telemetry" in lap and callable(lap["get_telemetry"]):
                    tel = lap["get_telemetry"]()

                if tel is None or (hasattr(tel, "empty") and tel.empty):
                    continue

                if "X" not in tel.columns or "Y" not in tel.columns:
                    continue

                # Clean missing / non-finite coordinates
                df_valid = tel.dropna(subset=["X", "Y"])
                
                x_num = pd.to_numeric(df_valid["X"], errors="coerce")
                y_num = pd.to_numeric(df_valid["Y"], errors="coerce")
                valid_mask = np.isfinite(x_num) & np.isfinite(y_num)
                df_valid = df_valid[valid_mask]

                if len(df_valid) >= 5:
                    x_list = df_valid["X"].astype(float).tolist()
                    y_list = df_valid["Y"].astype(float).tolist()
                    return list(zip(x_list, y_list))

            except Exception as e:
                logger.debug("Failed getting telemetry for candidate lap: %s", e)
                continue

        return None

    def _normalize_coordinates(self, raw_points: List[Tuple[float, float]]) -> List[Dict[str, float]]:
        """
        Normalize coordinates into 0..1 bounding box while strictly preserving aspect ratio.
        SVG coordinate system Y increases downward, so Y is inverted: y_norm = (y_max - y) / scale.
        """
        if not raw_points:
            return []

        x_vals = [p[0] for p in raw_points]
        y_vals = [p[1] for p in raw_points]

        x_min, x_max = min(x_vals), max(x_vals)
        y_min, y_max = min(y_vals), max(y_vals)

        dx = x_max - x_min
        dy = y_max - y_min

        scale = max(dx, dy)
        if scale == 0:
            scale = 1.0

        normalized = []
        for x, y in raw_points:
            x_norm = round((x - x_min) / scale, 5)
            y_norm = round((y_max - y) / scale, 5)
            normalized.append({"x": x_norm, "y": y_norm})

        return normalized
