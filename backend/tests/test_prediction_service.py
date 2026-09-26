from datetime import date, datetime
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Driver, Race, Session as F1Session, SessionResult, Team
from app.services.prediction_service.model_loader import ModelLoader, find_default_models_dir
from app.services.prediction_service.predictor import PredictionService


@pytest.fixture(scope="module")
def prediction_test_db():
    """Module-level in-memory SQLite DB with 2 teams, 2 drivers, and race session data."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionFactory()

    mclaren = Team(name="McLaren", constructor_code="mclaren", country="United Kingdom")
    redbull = Team(name="Red Bull Racing", constructor_code="red_bull", country="Austria")
    db.add_all([mclaren, redbull])
    db.commit()

    norris = Driver(driver_code="NOR", name="Lando Norris", country="United Kingdom", team_id=mclaren.id)
    verstappen = Driver(driver_code="VER", name="Max Verstappen", country="Netherlands", team_id=redbull.id)
    db.add_all([norris, verstappen])
    db.commit()

    race_2025_1 = Race(
        season=2025,
        round=1,
        race_name="Australian Grand Prix",
        circuit="Albert Park Circuit",
        country="Australia",
        race_date=date(2025, 3, 16),
    )
    db.add(race_2025_1)
    db.commit()

    fp1 = F1Session(race_id=race_2025_1.id, session_type="FP1", session_date=datetime(2025, 3, 14, 1, 30))
    race_sess = F1Session(race_id=race_2025_1.id, session_type="RACE", session_date=datetime(2025, 3, 16, 4, 0))
    db.add_all([fp1, race_sess])
    db.commit()

    res_nor = SessionResult(session_id=race_sess.id, driver_id=norris.id, position=1, lap_time=79.8, laps=58)
    res_ver = SessionResult(session_id=race_sess.id, driver_id=verstappen.id, position=2, lap_time=80.1, laps=58)
    db.add_all([res_nor, res_ver])
    db.commit()

    yield db
    db.close()


def test_model_loader_success():
    loader = ModelLoader()
    models = loader.load_models()
    assert "win_probability" in models
    assert "finish_position" in models
    assert "podium" in models
    assert "top5" in models


def test_model_loader_missing_dir(tmp_path: Path):
    loader = ModelLoader(models_dir=tmp_path / "nonexistent_models")
    with pytest.raises(FileNotFoundError, match="Model artifacts directory not found"):
        loader.load_models()


def test_prediction_service_valid_race(prediction_test_db):
    service = PredictionService(db=prediction_test_db)
    result = service.predict_race_stage(race_id=1, stage="POST_QUALIFYING")

    assert result["race_id"] == 1
    assert result["stage"] == "POST_QUALIFYING"
    assert len(result["predictions"]) == 2

    driver_codes = {p["driver_code"] for p in result["predictions"]}
    assert "NOR" in driver_codes
    assert "VER" in driver_codes

    total_share_prob = sum(p["race_share_probability"] for p in result["predictions"])
    assert pytest.approx(total_share_prob, abs=1e-3) == 1.0

    for pred in result["predictions"]:
        assert 0.0 <= pred["raw_win_probability"] <= 1.0
        assert 0.0 <= pred["race_share_probability"] <= 1.0
        assert 0.0 <= pred["podium_probability"] <= 1.0
        assert 0.0 <= pred["top5_probability"] <= 1.0
        assert 1.0 <= pred["predicted_finish_position"] <= 20.0

    assert result["data_availability"] is not None
    assert result["data_availability"]["historical_form"] is True


def test_prediction_service_invalid_stage(prediction_test_db):
    service = PredictionService(db=prediction_test_db)
    with pytest.raises(ValueError, match="Invalid prediction stage"):
        service.predict_race_stage(race_id=1, stage="POST_RACE")


def test_prediction_service_nonexistent_race(prediction_test_db):
    service = PredictionService(db=prediction_test_db)
    with pytest.raises(KeyError, match="Race with ID 99999 not found"):
        service.predict_race_stage(race_id=99999, stage="POST_QUALIFYING")
