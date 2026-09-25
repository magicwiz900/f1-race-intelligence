import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import fastf1
    from fastf1.core import Session as FastF1Session
    HAS_FASTF1 = True
except ImportError:
    HAS_FASTF1 = False
    FastF1Session = Any


class FastF1DataError(Exception):
    """Raised when an error occurs during FastF1 operations."""
    pass


class FastF1Service:
    """Service abstraction for FastF1 detailed session, telemetry, and lap timing data."""

    def __init__(self, cache_dir: Optional[str] = None, enable_cache: bool = True):
        self.enable_cache = enable_cache
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(os.getcwd()) / ".fastf1_cache"

        if HAS_FASTF1 and self.enable_cache:
            self._setup_cache()

    def _setup_cache(self) -> None:
        """Enable FastF1 cache directory if directory can be created."""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            fastf1.Cache.enable_cache(str(self.cache_dir))
            logger.info("FastF1 cache enabled at: %s", self.cache_dir)
        except Exception as e:
            logger.warning("Could not setup FastF1 cache at %s: %s", self.cache_dir, e)

    def is_available(self) -> bool:
        """Check if fastf1 library is available in current environment."""
        return HAS_FASTF1

    def get_session(self, year: int, grand_prix: str | int, session_type: str) -> FastF1Session:
        """Instantiate a FastF1 session object without loading heavy telemetry/laps yet."""
        if not HAS_FASTF1:
            raise FastF1DataError("FastF1 library is not installed.")

        try:
            logger.info("Getting FastF1 session for %s %s (%s)", year, grand_prix, session_type)
            session = fastf1.get_session(year, grand_prix, session_type)
            return session
        except Exception as e:
            raise FastF1DataError(f"Failed to get FastF1 session ({year}, {grand_prix}, {session_type}): {e}") from e

    def load_session(
        self,
        session: FastF1Session,
        laps: bool = True,
        telemetry: bool = False,
        weather: bool = False,
    ) -> None:
        """Load session data on demand."""
        if not HAS_FASTF1:
            raise FastF1DataError("FastF1 library is not installed.")

        try:
            logger.info("Loading FastF1 session data (laps=%s, telemetry=%s)", laps, telemetry)
            session.load(laps=laps, telemetry=telemetry, weather=weather)
        except Exception as e:
            raise FastF1DataError(f"Failed to load FastF1 session data: {e}") from e

    def extract_session_results(self, session: FastF1Session) -> List[Dict[str, Any]]:
        """Extract structured driver performance data (position, lap time, sector times, tyre compound)."""
        if not HAS_FASTF1:
            raise FastF1DataError("FastF1 library is not installed.")

        if not hasattr(session, "results") or session.results is None or session.results.empty:
            logger.warning("Session results not loaded or empty for session: %s", session)
            return []

        results = []
        for _, row in session.results.iterrows():
            driver_code = str(row.get("Abbreviation") or row.get("DriverNumber") or "")
            position = int(row.get("Position")) if not str(row.get("Position")).isna() and str(row.get("Position")).isdigit() else None
            
            # Extract lap time in seconds if available
            time_val = row.get("Time")
            lap_time_sec = time_val.total_seconds() if hasattr(time_val, "total_seconds") else None

            # FastF1 session results summary row:
            res_dict = {
                "driver_code": driver_code,
                "position": position,
                "lap_time": lap_time_sec,
                "sector_1": None,
                "sector_2": None,
                "sector_3": None,
                "tyre": None,
                "laps": int(row.get("Laps")) if "Laps" in row and not str(row.get("Laps")).isna() and str(row.get("Laps")).isdigit() else None,
            }

            # If detailed laps exist, enrich with best lap sector times and compound
            if hasattr(session, "laps") and session.laps is not None and not session.laps.empty:
                driver_laps = session.laps.pick_driver(driver_code)
                if not driver_laps.empty:
                    fastest_lap = driver_laps.pick_fastest()
                    if fastest_lap is not None and not fastest_lap.empty:
                        s1 = fastest_lap.get("Sector1Time")
                        s2 = fastest_lap.get("Sector2Time")
                        s3 = fastest_lap.get("Sector3Time")

                        res_dict["sector_1"] = s1.total_seconds() if hasattr(s1, "total_seconds") else None
                        res_dict["sector_2"] = s2.total_seconds() if hasattr(s2, "total_seconds") else None
                        res_dict["sector_3"] = s3.total_seconds() if hasattr(s3, "total_seconds") else None
                        res_dict["tyre"] = str(fastest_lap.get("Compound")) if fastest_lap.get("Compound") else None
                        
                        if res_dict["lap_time"] is None:
                            lap_t = fastest_lap.get("LapTime")
                            res_dict["lap_time"] = lap_t.total_seconds() if hasattr(lap_t, "total_seconds") else None

            results.append(res_dict)

        return results
