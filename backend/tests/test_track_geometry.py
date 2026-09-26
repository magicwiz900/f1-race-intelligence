from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.services.f1_data.track_geometry import (
    TrackGeometryError,
    TrackGeometryService,
    TrackGeometryUnavailableError,
)


@pytest.fixture(autouse=True)
def clear_geometry_cache():
    """Clear in-memory geometry cache before each test."""
    TrackGeometryService.clear_cache()
    yield
    TrackGeometryService.clear_cache()


def test_get_track_geometry_success(client: TestClient):
    """Test successful GET /api/races/{race_id}/track-geometry with mocked FastF1 telemetry."""
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    # Mock telemetry DataFrame with valid X and Y coordinates
    mock_telemetry = pd.DataFrame({
        "X": [1000.0, 1500.0, 2000.0, 1500.0, 1000.0, 1000.0],
        "Y": [2000.0, 2500.0, 3000.0, 3500.0, 3000.0, 2000.0],
    })

    mock_lap = MagicMock()
    mock_lap.empty = False
    mock_lap.get_telemetry.return_value = mock_telemetry

    mock_laps = MagicMock()
    mock_laps.empty = False
    mock_laps.pick_fastest.return_value = mock_lap

    mock_session = MagicMock()
    mock_session.laps = mock_laps

    with patch("app.services.f1_data.track_geometry.FastF1Service") as mock_service_cls:
        mock_service_inst = MagicMock()
        mock_service_cls.return_value = mock_service_inst
        mock_service_inst.is_available.return_value = True
        mock_service_inst.get_session.return_value = mock_session
        mock_service_inst.load_session.return_value = None

        response = client.get(f"/api/races/{race_id}/track-geometry")

    assert response.status_code == 200
    data = response.json()
    assert data["race_id"] == race_id
    assert data["season"] == 2025
    assert data["race_name"] == "Australian Grand Prix"
    assert data["circuit"] == "Albert Park Circuit"
    assert data["source"] == "FastF1 telemetry"
    assert data["session_type"] == "QUALIFYING"
    assert data["coordinate_system"] == "normalized"
    assert data["point_count"] == 6
    assert isinstance(data["points"], list)

    # Validate coordinate bounds
    for pt in data["points"]:
        assert 0.0 <= pt["x"] <= 1.0
        assert 0.0 <= pt["y"] <= 1.0


def test_get_track_geometry_race_not_found(client: TestClient):
    """Test 404 response for nonexistent race ID."""
    response = client.get("/api/races/99999/track-geometry")
    assert response.status_code == 404
    data = response.json()
    assert "Race with ID 99999 not found" in data["detail"]


def test_get_track_geometry_telemetry_unavailable(client: TestClient):
    """Test non-500 response when FastF1 telemetry is unavailable."""
    races = client.get("/api/races").json()
    race_id = races[0]["id"]

    with patch.object(
        TrackGeometryService,
        "get_track_geometry",
        side_effect=TrackGeometryUnavailableError("Telemetry not found"),
    ):
        response = client.get(f"/api/races/{race_id}/track-geometry")

    assert response.status_code == 404
    data = response.json()
    assert "Track geometry telemetry unavailable" in data["detail"]


def test_coordinate_cleaning_and_aspect_ratio_normalization():
    """Test coordinate cleaning and aspect-ratio preserving normalization."""
    service = TrackGeometryService()

    raw_points = [
        (100.0, 500.0),
        (200.0, 400.0),
        (300.0, 300.0),
        (200.0, 200.0),
        (100.0, 100.0),
    ]

    normalized = service._normalize_coordinates(raw_points)
    assert len(normalized) == 5

    # Point 0: (100, 500) -> x_norm = 0.0, y_norm = 0.0 (top in SVG)
    assert normalized[0]["x"] == 0.0
    assert normalized[0]["y"] == 0.0

    # Point 2: (300, 300) -> x_norm = (300-100)/400 = 0.5, y_norm = (500-300)/400 = 0.5
    assert normalized[2]["x"] == 0.5
    assert normalized[2]["y"] == 0.5

    # Point 4: (100, 100) -> x_norm = 0.0, y_norm = (500-100)/400 = 1.0 (bottom in SVG)
    assert normalized[4]["x"] == 0.0
    assert normalized[4]["y"] == 1.0


def test_extract_lap_telemetry_filters_invalid_values():
    """Test _extract_lap_telemetry drops rows with NaN/Inf values."""
    service = TrackGeometryService()

    df_dirty = pd.DataFrame({
        "X": [100.0, np.nan, 200.0, np.inf, 300.0, 400.0, 500.0, 600.0],
        "Y": [100.0, 200.0, 200.0, 400.0, 300.0, 400.0, 500.0, 600.0],
    })

    mock_lap = MagicMock()
    mock_lap.empty = False
    mock_lap.get_telemetry.return_value = df_dirty

    mock_session = MagicMock()
    mock_session.laps.empty = False
    mock_session.laps.pick_fastest.return_value = mock_lap

    extracted = service._extract_lap_telemetry(mock_session)
    assert extracted is not None
    assert len(extracted) == 6  # 6 valid rows after dropping NaN and inf


def test_track_geometry_service_caching():
    """Test in-memory cache avoids duplicate FastF1 lookups."""
    service = TrackGeometryService()

    with patch.object(
        service, "_extract_raw_geometry", return_value=("QUALIFYING", [(10.0, 20.0), (30.0, 40.0), (50.0, 60.0), (70.0, 80.0), (90.0, 100.0)])
    ) as mock_extract:
        res1 = service.get_track_geometry(
            race_id=1, season=2025, round_num=1, race_name="Australian GP", circuit="Albert Park"
        )
        res2 = service.get_track_geometry(
            race_id=1, season=2025, round_num=1, race_name="Australian GP", circuit="Albert Park"
        )

        assert mock_extract.call_count == 1
        assert res1 == res2
