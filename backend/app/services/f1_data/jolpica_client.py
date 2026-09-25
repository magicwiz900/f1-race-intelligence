import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class JolpicaAPIError(Exception):
    """Base exception for Jolpica API operations."""
    pass


class JolpicaHTTPError(JolpicaAPIError):
    """Raised when an HTTP error occurs (e.g. status code 4xx, 5xx)."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Jolpica HTTP {status_code}: {message}")


class JolpicaParseError(JolpicaAPIError):
    """Raised when Jolpica API response payload cannot be parsed."""
    pass


class JolpicaClient:
    """HTTP client for retrieving F1 data from the Jolpica Ergast-compatible API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
        httpx_client: Optional[httpx.Client] = None,
    ):
        raw_url = base_url or settings.F1_API_BASE_URL
        self.base_url = raw_url.rstrip("/")
        self.timeout = timeout
        self._external_client = httpx_client

    def _get_client(self) -> httpx.Client:
        if self._external_client:
            return self._external_client
        return httpx.Client(timeout=self.timeout)

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform GET request against specified endpoint and return raw parsed JSON."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        query_params = {k: v for k, v in (params or {}).items() if v is not None}

        client = self._get_client()
        should_close = self._external_client is None

        try:
            logger.debug("Requesting Jolpica API: %s with params %s", url, query_params)
            response = client.get(url, params=query_params)
            
            if response.status_code >= 400:
                raise JolpicaHTTPError(
                    status_code=response.status_code,
                    message=f"Request to {url} failed with status {response.status_code}",
                )
            
            try:
                data = response.json()
            except Exception as e:
                raise JolpicaParseError(f"Failed to parse JSON response from {url}: {e}") from e

            if not isinstance(data, dict) or "MRData" not in data:
                raise JolpicaParseError(f"Invalid Jolpica response structure from {url}: missing 'MRData'")

            return data["MRData"]

        except httpx.RequestError as e:
            raise JolpicaAPIError(f"Network error accessing Jolpica API at {url}: {e}") from e
        finally:
            if should_close:
                client.close()

    def get_seasons(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve list of F1 seasons."""
        mrdata = self._request("seasons.json", params={"limit": limit, "offset": offset})
        try:
            return mrdata.get("SeasonTable", {}).get("Seasons", [])
        except AttributeError as e:
            raise JolpicaParseError(f"Malformed SeasonTable structure: {e}") from e

    def get_races(self, season: int | str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieve race calendar for a given season."""
        endpoint = f"{season}.json"
        mrdata = self._request(endpoint, params={"limit": limit, "offset": offset})
        try:
            return mrdata.get("RaceTable", {}).get("Races", [])
        except AttributeError as e:
            raise JolpicaParseError(f"Malformed RaceTable structure: {e}") from e

    def get_race_results(
        self,
        season: int | str,
        round_num: Optional[int | str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve race results for a season (or specific round of a season)."""
        if round_num is not None:
            endpoint = f"{season}/{round_num}/results.json"
        else:
            endpoint = f"{season}/results.json"

        mrdata = self._request(endpoint, params={"limit": limit, "offset": offset})
        try:
            return mrdata.get("RaceTable", {}).get("Races", [])
        except AttributeError as e:
            raise JolpicaParseError(f"Malformed RaceTable structure for results: {e}") from e

    def get_all_race_results(self, season: int | str) -> List[Dict[str, Any]]:
        """Retrieve ALL race results for a season, handling pagination automatically."""
        offset = 0
        limit = 100
        all_races_map: Dict[str, Dict[str, Any]] = {}

        while True:
            endpoint = f"{season}/results.json"
            mrdata = self._request(endpoint, params={"limit": limit, "offset": offset})
            
            races = mrdata.get("RaceTable", {}).get("Races", [])
            if not races:
                break

            total_str = mrdata.get("total", "0")
            try:
                total = int(total_str)
            except ValueError:
                total = 0

            for race in races:
                round_key = str(race.get("round"))
                if round_key not in all_races_map:
                    all_races_map[round_key] = {
                        **race,
                        "Results": list(race.get("Results", [])),
                    }
                else:
                    existing_results = all_races_map[round_key]["Results"]
                    existing_results.extend(race.get("Results", []))

            offset += limit
            if total > 0 and offset >= total:
                break
            if len(races) < limit and total == 0:
                break

        # Return ordered list by round
        sorted_rounds = sorted(all_races_map.keys(), key=lambda r: int(r) if r.isdigit() else 0)
        return [all_races_map[r] for r in sorted_rounds]

    def get_drivers(
        self,
        season: Optional[int | str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve list of drivers (optionally filtered by season)."""
        endpoint = f"{season}/drivers.json" if season is not None else "drivers.json"
        mrdata = self._request(endpoint, params={"limit": limit, "offset": offset})
        try:
            return mrdata.get("DriverTable", {}).get("Drivers", [])
        except AttributeError as e:
            raise JolpicaParseError(f"Malformed DriverTable structure: {e}") from e

    def get_constructors(
        self,
        season: Optional[int | str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Retrieve list of constructors/teams (optionally filtered by season)."""
        endpoint = f"{season}/constructors.json" if season is not None else "constructors.json"
        mrdata = self._request(endpoint, params={"limit": limit, "offset": offset})
        try:
            return mrdata.get("ConstructorTable", {}).get("Constructors", [])
        except AttributeError as e:
            raise JolpicaParseError(f"Malformed ConstructorTable structure: {e}") from e
