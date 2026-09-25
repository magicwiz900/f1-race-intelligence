from datetime import date, datetime, timezone
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def parse_time_to_seconds(time_val: Any) -> Optional[float]:
    """Parse time representations (millis, time string like '1:32.608' or float/int) into seconds float."""
    if time_val is None:
        return None
    if isinstance(time_val, (int, float)):
        return float(time_val)

    if isinstance(time_val, dict):
        if "millis" in time_val and time_val["millis"] is not None:
            try:
                return float(time_val["millis"]) / 1000.0
            except (ValueError, TypeError):
                pass
        time_str = time_val.get("time")
    else:
        time_str = str(time_val)

    if not time_str or not isinstance(time_str, str):
        return None

    time_str = time_str.strip()
    if not time_str:
        return None

    # Try standard string format e.g. "1:31:44.742", "1:32.608", "92.608"
    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600.0 + minutes * 60.0 + seconds
        elif len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60.0 + seconds
        elif len(parts) == 1:
            return float(parts[0])
    except (ValueError, TypeError):
        logger.debug("Could not parse time string: %s", time_str)
        return None

    return None


def parse_iso_datetime(date_str: Optional[str], time_str: Optional[str] = None) -> Optional[datetime]:
    """Parse date string and optional time string into datetime object."""
    if not date_str:
        return None

    try:
        if time_str:
            clean_time = time_str.rstrip("Z")
            dt_str = f"{date_str}T{clean_time}"
            return datetime.fromisoformat(dt_str)
        else:
            d = date.fromisoformat(date_str)
            return datetime(d.year, d.month, d.day)
    except (ValueError, TypeError) as e:
        logger.debug("Failed to parse datetime from %s / %s: %e", date_str, time_str, e)
        return None


def transform_team(constructor_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Transform Jolpica Constructor dictionary into Team database fields."""
    name = constructor_dict.get("name", "").strip()
    constructor_code = constructor_dict.get("constructorId", "").strip() or None
    country = constructor_dict.get("nationality", "").strip() or None

    return {
        "name": name,
        "constructor_code": constructor_code,
        "country": country,
    }


def transform_driver(driver_dict: Dict[str, Any], team_id: Optional[int] = None) -> Dict[str, Any]:
    """Transform Jolpica Driver dictionary into Driver database fields."""
    code = (driver_dict.get("code") or "").strip()
    driver_id = (driver_dict.get("driverId") or "").strip()
    given_name = (driver_dict.get("givenName") or "").strip()
    family_name = (driver_dict.get("familyName") or "").strip()
    nationality = (driver_dict.get("nationality") or "").strip()

    name = f"{given_name} {family_name}".strip() if (given_name or family_name) else driver_id

    # If code is missing (common for older/niche drivers), fallback to uppercase driver_id or family_name
    if not code:
        if driver_id:
            code = driver_id.upper()[:10]
        elif family_name:
            code = family_name.upper()[:10]
        else:
            code = name.upper()[:10]

    return {
        "driver_code": code[:10],
        "name": name,
        "country": nationality or None,
        "team_id": team_id,
    }


def transform_race(race_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Transform Jolpica Race dictionary into Race database fields and session info."""
    season = int(race_dict["season"])
    round_num = int(race_dict["round"])
    race_name = race_dict.get("raceName", "").strip()

    circuit_info = race_dict.get("Circuit", {})
    circuit_name = circuit_info.get("circuitName", "Unknown Circuit").strip()
    location_info = circuit_info.get("Location", {})
    country = location_info.get("country", "").strip() or None

    race_date = date.fromisoformat(race_dict["date"])

    # Extract session definitions
    sessions_info: List[Dict[str, Any]] = []

    # Sessions mapping dictionary: Jolpica key -> session_type name
    session_keys = [
        ("FirstPractice", "FP1"),
        ("SecondPractice", "FP2"),
        ("ThirdPractice", "FP3"),
        ("Qualifying", "QUALIFYING"),
    ]

    for key, stype in session_keys:
        if key in race_dict and isinstance(race_dict[key], dict):
            sdata = race_dict[key]
            s_date = sdata.get("date")
            s_time = sdata.get("time")
            s_dt = parse_iso_datetime(s_date, s_time)
            sessions_info.append({
                "session_type": stype,
                "session_date": s_dt,
            })

    # Add main RACE session
    race_dt = parse_iso_datetime(race_dict.get("date"), race_dict.get("time"))
    sessions_info.append({
        "session_type": "RACE",
        "session_date": race_dt,
    })

    return {
        "season": season,
        "round": round_num,
        "race_name": race_name,
        "circuit": circuit_name,
        "country": country,
        "race_date": race_date,
        "sessions_info": sessions_info,
    }


def transform_session_result(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Transform Jolpica Result item into SessionResult database fields."""
    pos_raw = result_dict.get("position")
    position = None
    if pos_raw is not None:
        try:
            position = int(pos_raw)
        except (ValueError, TypeError):
            position = None

    laps_raw = result_dict.get("laps")
    laps = None
    if laps_raw is not None:
        try:
            laps = int(laps_raw)
        except (ValueError, TypeError):
            laps = None

    # Lap time resolution:
    # Prefer FastestLap.Time.time if available, else Time.time/Time.millis
    lap_time = None
    fastest_lap = result_dict.get("FastestLap")
    if isinstance(fastest_lap, dict) and "Time" in fastest_lap:
        lap_time = parse_time_to_seconds(fastest_lap["Time"])

    if lap_time is None and "Time" in result_dict:
        lap_time = parse_time_to_seconds(result_dict["Time"])

    return {
        "position": position,
        "laps": laps,
        "lap_time": lap_time,
        "sector_1": None,
        "sector_2": None,
        "sector_3": None,
        "tyre": None,
    }
