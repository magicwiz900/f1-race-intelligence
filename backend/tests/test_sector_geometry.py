from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.services.f1_data.sector_geometry import (
    SectorGeometryError,
    SectorGeometryService,
    SectorGeometryUnavailableError,
)


@pytest.fixture(autouse=True)
def clear_sector_geometry_cache():
    """Clear in-memory sector geometry cache before each test."""
    SectorGeometryService.clear_cache()
    yield
    SectorGeometryService.clear_cache()


def test_get_sector_geometry_success(client: TestClient):
    """Test successful GET /api/races/{race_id}/sector-geometry with mocked FastF1 telemetry."""
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    # Mock telemetry DataFrame with X, Y, Distance, and TimeSec/Time
    times_sec = np.linspace(0, 75.0, 30)
    distances = np.linspace(0, 5000.0, 30)
    x_coords = np.linspace(1000.0, 4000.0, 30)
    y_coords = np.linspace(2000.0, 5000.0, 30)

    mock_telemetry = pd.DataFrame({
        "TimeSec": times_sec,
        "Distance": distances,
        "X": x_coords,
        "Y": y_coords,
    })

    mock_lap = MagicMock()
    mock_lap.empty = False
    mock_lap.get.side_effect = lambda key: {
        "Sector1Time": pd.Timedelta("25s"),
        "Sector2Time": pd.Timedelta("15s"),
        "Sector3Time": pd.Timedelta("35s"),
    }.get(key)
    mock_lap.get_telemetry.return_value = mock_telemetry

    mock_laps = MagicMock()
    mock_laps.empty = False
    mock_laps.pick_fastest.return_value = mock_lap

    mock_session = MagicMock()
    mock_session.laps = mock_laps

    with patch("app.services.f1_data.sector_geometry.FastF1Service") as mock_service_cls:
        mock_service_inst = MagicMock()
        mock_service_cls.return_value = mock_service_inst
        mock_service_inst.is_available.return_value = True
        mock_service_inst.get_session.return_value = mock_session
        mock_service_inst.load_session.return_value = None

        response = client.get(f"/api/races/{race_id}/sector-geometry")

    assert response.status_code == 200
    data = response.json()

    # 1. Valid sector geometry response metadata
    assert data["race_id"] == race_id
    assert data["season"] == 2025
    assert data["race_name"] == "Australian Grand Prix"
    assert data["circuit"] == "Albert Park Circuit"
    assert data["source"] == "FastF1 telemetry"
    assert data["session_type"] == "QUALIFYING"
    assert data["coordinate_system"] == "normalized"
    assert data["total_distance"] == 5000.0

    sectors = data["sectors"]
    # 2. Exactly three sectors
    assert len(sectors) == 3

    # 3. Sector numbers are 1, 2, 3
    assert [s["sector"] for s in sectors] == [1, 2, 3]

    s1, s2, s3 = sectors[0], sectors[1], sectors[2]

    # 7. Each sector contains sufficient points
    assert len(s1["points"]) >= 2
    assert len(s2["points"]) >= 2
    assert len(s3["points"]) >= 2

    # 4 & 5. All coordinates are numeric and finite, 6. Normalized (0..1)
    for s in sectors:
        for pt in s["points"]:
            assert isinstance(pt["x"], (int, float))
            assert isinstance(pt["y"], (int, float))
            assert np.isfinite(pt["x"])
            assert np.isfinite(pt["y"])
            assert 0.0 <= pt["x"] <= 1.0
            assert 0.0 <= pt["y"] <= 1.0

    # 8. Sector distances are monotonically increasing
    assert 0.0 == s1["start_distance"] < s1["end_distance"]
    assert s1["end_distance"] < s2["end_distance"]
    assert s2["end_distance"] <= s3["end_distance"]

    # 9. start_distance < end_distance for each sector
    for s in sectors:
        assert s["start_distance"] < s["end_distance"]
        assert s["start_relative_distance"] < s["end_relative_distance"]

    # 10. S1 ends where S2 begins
    assert s1["end_distance"] == s2["start_distance"]
    assert s1["end_relative_distance"] == s2["start_relative_distance"]
    assert s1["points"][-1] == s2["points"][0]

    # 11. S2 ends where S3 begins
    assert s2["end_distance"] == s3["start_distance"]
    assert s2["end_relative_distance"] == s3["start_relative_distance"]
    assert s2["points"][-1] == s3["points"][0]

    # 12. S3 ends at total lap distance
    assert s3["end_distance"] == data["total_distance"]
    assert s3["end_relative_distance"] == 1.0

    # 13. Boundaries are NOT simple 1/3 (0.333) and 2/3 (0.667) assumptions
    # S1 time ratio = 25/75 = 0.333, S2 time ratio = 15/75 = 0.200 (so S2 end is 40/75 = 0.533)
    assert abs(s2["end_relative_distance"] - 0.667) > 0.05


def test_get_sector_geometry_race_not_found(client: TestClient):
    """Test 404 response for nonexistent race ID."""
    response = client.get("/api/races/99999/sector-geometry")
    assert response.status_code == 404
    data = response.json()
    assert "Race with ID 99999 not found" in data["detail"]


def test_get_sector_geometry_telemetry_unavailable(client: TestClient):
    """Test 404 response when sector telemetry is unavailable."""
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    with patch.object(
        SectorGeometryService,
        "get_sector_geometry",
        side_effect=SectorGeometryUnavailableError("No telemetry"),
    ):
        response = client.get(f"/api/races/{race_id}/sector-geometry")

    assert response.status_code == 404
    data = response.json()
    assert "Sector geometry telemetry unavailable" in data["detail"]


def test_session_fallback(client: TestClient):
    """Test fallback from QUALIFYING to FP3 when QUALIFYING has no telemetry."""
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    times_sec = np.linspace(0, 80.0, 20)
    distances = np.linspace(0, 5200.0, 20)

    mock_telemetry = pd.DataFrame({
        "TimeSec": times_sec,
        "Distance": distances,
        "X": np.linspace(100, 500, 20),
        "Y": np.linspace(100, 500, 20),
    })

    mock_fp3_lap = MagicMock()
    mock_fp3_lap.empty = False
    mock_fp3_lap.get.side_effect = lambda key: {
        "Sector1Time": 26.0,
        "Sector2Time": 20.0,
        "Sector3Time": 34.0,
    }.get(key)
    mock_fp3_lap.get_telemetry.return_value = mock_telemetry

    q_session = MagicMock()
    q_session.laps = MagicMock()
    q_session.laps.empty = True

    fp3_session = MagicMock()
    fp3_session.laps = MagicMock()
    fp3_session.laps.empty = False
    fp3_session.laps.pick_fastest.return_value = mock_fp3_lap

    def mock_get_session(year, grand_prix, session_type):
        if session_type == "Q":
            return q_session
        elif session_type == "FP3":
            return fp3_session
        raise Exception("Session unavailable")

    with patch("app.services.f1_data.sector_geometry.FastF1Service") as mock_service_cls:
        mock_service_inst = MagicMock()
        mock_service_cls.return_value = mock_service_inst
        mock_service_inst.is_available.return_value = True
        mock_service_inst.get_session.side_effect = mock_get_session
        mock_service_inst.load_session.return_value = None

        response = client.get(f"/api/races/{race_id}/sector-geometry")

    assert response.status_code == 200
    data = response.json()
    assert data["session_type"] == "FP3"
    assert len(data["sectors"]) == 3


def test_sector_geometry_service_caching():
    """Test in-memory cache avoids duplicate FastF1 lookups."""
    service = SectorGeometryService()

    fake_sectors = [
        {"sector": 1, "start_distance": 0.0, "end_distance": 1000.0, "start_relative_distance": 0.0, "end_relative_distance": 0.2, "points": [{"x": 0.1, "y": 0.1}]},
        {"sector": 2, "start_distance": 1000.0, "end_distance": 3000.0, "start_relative_distance": 0.2, "end_relative_distance": 0.6, "points": [{"x": 0.1, "y": 0.1}]},
        {"sector": 3, "start_distance": 3000.0, "end_distance": 5000.0, "start_relative_distance": 0.6, "end_relative_distance": 1.0, "points": [{"x": 0.1, "y": 0.1}]},
    ]

    with patch.object(
        service, "_extract_raw_sector_geometry", return_value=("QUALIFYING", 5000.0, fake_sectors)
    ) as mock_extract:
        res1 = service.get_sector_geometry(
            race_id=1, season=2025, round_num=1, race_name="Australian GP", circuit="Albert Park"
        )
        res2 = service.get_sector_geometry(
            race_id=1, season=2025, round_num=1, race_name="Australian GP", circuit="Albert Park"
        )

        assert mock_extract.call_count == 1
        assert res1 == res2
