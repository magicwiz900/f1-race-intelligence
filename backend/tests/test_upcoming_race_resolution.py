from datetime import date, datetime
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.main import app
from app.models import Base, Driver, Race, Session as F1Session, SessionResult, Team
from app.services.prediction_service.predictor import PredictionService
from app.services.race_service import get_next_upcoming_race
from ml.stages import PredictionStage


@pytest.fixture
def calendar_test_db():
    """
    Sets up an in-memory database with races spanning multiple seasons:
    - 2024 Round 1 (Bahrain GP): 2024-03-02 (Completed)
    - 2025 Round 1 (Australian GP): 2025-03-16 (Completed)
    - 2025 Round 2 (Chinese GP): 2025-03-23 (Upcoming in 2025)
    - 2026 Round 1 (Australian GP): 2026-03-15 (Future season upcoming)
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionFactory()

    mclaren = Team(name="McLaren", constructor_code="mclaren", country="United Kingdom")
    redbull = Team(name="Red Bull Racing", constructor_code="red_bull", country="Austria")
    db.add_all([mclaren, redbull])
    db.commit()

    norris = Driver(driver_code="NOR", name="Lando Norris", country="United Kingdom", team_id=mclaren.id)
    verstappen = Driver(driver_code="VER", name="Max Verstappen", country="Netherlands", team_id=redbull.id)
    rookie = Driver(driver_code="ROO", name="Rookie Driver", country="UK", team_id=mclaren.id) # Cold-start driver
    db.add_all([norris, verstappen, rookie])
    db.commit()

    # 2024 Round 1
    r2024_1 = Race(season=2024, round=1, race_name="Bahrain GP", circuit="Bahrain Circuit", country="Bahrain", race_date=date(2024, 3, 2))
    # 2025 Round 1
    r2025_1 = Race(season=2025, round=1, race_name="Australian GP", circuit="Albert Park", country="Australia", race_date=date(2025, 3, 16))
    # 2025 Round 2
    r2025_2 = Race(season=2025, round=2, race_name="Chinese GP", circuit="Shanghai Circuit", country="China", race_date=date(2025, 3, 23))
    # 2026 Round 1
    r2026_1 = Race(season=2026, round=1, race_name="Australian GP", circuit="Albert Park", country="Australia", race_date=date(2026, 3, 15))

    db.add_all([r2024_1, r2025_1, r2025_2, r2026_1])
    db.commit()

    # Add results for 2024 Round 1 and 2025 Round 1
    s2024_1 = F1Session(race_id=r2024_1.id, session_type="RACE", session_date=datetime(2024, 3, 2, 15, 0))
    s2025_1 = F1Session(race_id=r2025_1.id, session_type="RACE", session_date=datetime(2025, 3, 16, 4, 0))
    db.add_all([s2024_1, s2025_1])
    db.commit()

    db.add_all([
        SessionResult(session_id=s2024_1.id, driver_id=verstappen.id, position=1),
        SessionResult(session_id=s2024_1.id, driver_id=norris.id, position=2),

        SessionResult(session_id=s2025_1.id, driver_id=norris.id, position=1),
        SessionResult(session_id=s2025_1.id, driver_id=verstappen.id, position=2),
    ])
    db.commit()

    yield db
    db.close()


def test_get_next_upcoming_race_chronological(calendar_test_db):
    """Test 1 & 2: Chronological next race resolution based on reference date."""
    # As of 2025-03-10: Next race is 2025 Round 1 (2025-03-16)
    race_mar10 = get_next_upcoming_race(calendar_test_db, as_of_date=date(2025, 3, 10))
    assert race_mar10 is not None
    assert race_mar10.season == 2025
    assert race_mar10.round == 1

    # As of 2025-03-20: Next race is 2025 Round 2 (2025-03-23)
    race_mar20 = get_next_upcoming_race(calendar_test_db, as_of_date=date(2025, 3, 20))
    assert race_mar20 is not None
    assert race_mar20.season == 2025
    assert race_mar20.round == 2

    # As of 2026-01-01: Next race is 2026 Round 1 (2026-03-15)
    race_2026 = get_next_upcoming_race(calendar_test_db, as_of_date=date(2026, 1, 1))
    assert race_2026 is not None
    assert race_2026.season == 2026
    assert race_2026.round == 1

    # As of 2099-01-01: No races in DB -> returns None
    race_far_future = get_next_upcoming_race(calendar_test_db, as_of_date=date(2099, 1, 1))
    assert race_far_future is None


def test_cross_season_pre_fp1_prediction(calendar_test_db):
    """Test 7: PRE_FP1 prediction for future season (2026 Round 1) uses prior seasons (2024, 2025) safely."""
    r2026_1 = calendar_test_db.query(Race).filter_by(season=2026, round=1).one()

    service = PredictionService(db=calendar_test_db)
    result = service.predict_race_stage(race_id=r2026_1.id, stage="PRE_FP1")

    assert result["race_id"] == r2026_1.id
    assert result["stage"] == "PRE_FP1"
    assert len(result["predictions"]) > 0

    for pred in result["predictions"]:
        assert 0.0 <= pred["raw_win_probability"] <= 1.0
        assert 0.0 <= pred["race_share_probability"] <= 1.0
        assert np.isfinite(pred["predicted_finish_position"])


def test_cold_start_driver_handling(calendar_test_db):
    """Test 8: Rookie driver with zero historical performance gets valid predictions via SimpleImputer."""
    r2026_1 = calendar_test_db.query(Race).filter_by(season=2026, round=1).one()

    service = PredictionService(db=calendar_test_db)
    result = service.predict_race_stage(race_id=r2026_1.id, stage="PRE_FP1")

    rookie_pred = next((p for p in result["predictions"] if p["driver_code"] == "ROO"), None)
    assert rookie_pred is not None
    assert 0.0 <= rookie_pred["race_share_probability"] <= 1.0
    assert np.isfinite(rookie_pred["predicted_finish_position"])


def test_api_upcoming_race_endpoints(calendar_test_db):
    """Test 9: Integration tests for /api/races/upcoming and /api/races/upcoming/predictions."""
    def _override_get_db():
        try:
            yield calendar_test_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as client:
            # 1. GET /api/races/upcoming?as_of_date=2025-03-20
            res = client.get("/api/races/upcoming?as_of_date=2025-03-20")
            assert res.status_code == 200
            data = res.json()
            assert data["season"] == 2025
            assert data["round"] == 2
            assert data["race_name"] == "Chinese GP"

            # 2. GET /api/races/upcoming/predictions?as_of_date=2025-03-20
            res_pred = client.get("/api/races/upcoming/predictions?as_of_date=2025-03-20&stage=PRE_FP1")
            assert res_pred.status_code == 200
            data_pred = res_pred.json()
            assert data_pred["stage"] == "PRE_FP1"
            assert data_pred["season"] == 2025
            assert data_pred["round"] == 2
            assert len(data_pred["predictions"]) > 0

            # 3. Nonexistent future date returns 404
            res_404 = client.get("/api/races/upcoming?as_of_date=2099-01-01")
            assert res_404.status_code == 404
            assert "No upcoming races found in calendar" in res_404.json()["detail"]

    finally:
        app.dependency_overrides.clear()
