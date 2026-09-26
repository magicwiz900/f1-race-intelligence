from datetime import date, datetime
from pathlib import Path
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
from app.services.prediction_service.feature_adapter import FeatureAdapter
from app.services.prediction_service.predictor import PredictionService
from ml.stages import PredictionStage


@pytest.fixture
def upcoming_race_db():
    """
    Sets up an in-memory database containing:
    - 2024 Round 1 (Bahrain GP) with completed race results.
    - 2024 Round 2 (Saudi GP) with completed race results.
    - 2025 Round 1 (Australian GP) with NO session results (upcoming race).
    - 2025 Round 2 (Chinese GP) with NO session results (future upcoming race).
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionFactory()

    mclaren = Team(name="McLaren", constructor_code="mclaren", country="United Kingdom")
    redbull = Team(name="Red Bull Racing", constructor_code="red_bull", country="Austria")
    ferrari = Team(name="Scuderia Ferrari", constructor_code="ferrari", country="Italy")
    db.add_all([mclaren, redbull, ferrari])
    db.commit()

    norris = Driver(driver_code="NOR", name="Lando Norris", country="United Kingdom", team_id=mclaren.id)
    verstappen = Driver(driver_code="VER", name="Max Verstappen", country="Netherlands", team_id=redbull.id)
    leclerc = Driver(driver_code="LEC", name="Charles Leclerc", country="Monaco", team_id=ferrari.id)
    db.add_all([norris, verstappen, leclerc])
    db.commit()

    # 2024 Round 1 - Bahrain
    r2024_1 = Race(season=2024, round=1, race_name="Bahrain Grand Prix", circuit="Bahrain International Circuit", country="Bahrain", race_date=date(2024, 3, 2))
    # 2024 Round 2 - Saudi
    r2024_2 = Race(season=2024, round=2, race_name="Saudi Arabian Grand Prix", circuit="Jeddah Corniche Circuit", country="Saudi Arabia", race_date=date(2024, 3, 9))

    # 2025 Round 1 - Australia (Upcoming Target Race)
    r2025_1 = Race(season=2025, round=1, race_name="Australian Grand Prix", circuit="Albert Park Circuit", country="Australia", race_date=date(2025, 3, 16))
    # 2025 Round 2 - China (Future Race)
    r2025_2 = Race(season=2025, round=2, race_name="Chinese Grand Prix", circuit="Shanghai International Circuit", country="China", race_date=date(2025, 3, 23))

    db.add_all([r2024_1, r2024_2, r2025_1, r2025_2])
    db.commit()

    # Add 2024 session results
    s2024_1 = F1Session(race_id=r2024_1.id, session_type="RACE", session_date=datetime(2024, 3, 2, 15, 0))
    s2024_2 = F1Session(race_id=r2024_2.id, session_type="RACE", session_date=datetime(2024, 3, 9, 17, 0))
    db.add_all([s2024_1, s2024_2])
    db.commit()

    db.add_all([
        SessionResult(session_id=s2024_1.id, driver_id=verstappen.id, position=1, lap_time=5400.0, laps=57),
        SessionResult(session_id=s2024_1.id, driver_id=norris.id, position=2, lap_time=5420.0, laps=57),
        SessionResult(session_id=s2024_1.id, driver_id=leclerc.id, position=3, lap_time=5430.0, laps=57),

        SessionResult(session_id=s2024_2.id, driver_id=verstappen.id, position=1, lap_time=5000.0, laps=50),
        SessionResult(session_id=s2024_2.id, driver_id=leclerc.id, position=2, lap_time=5015.0, laps=50),
        SessionResult(session_id=s2024_2.id, driver_id=norris.id, position=3, lap_time=5025.0, laps=50),
    ])
    db.commit()

    yield db
    db.close()


def test_leakage_1_no_session_data_required(upcoming_race_db):
    """Test 1: A future race with zero session results must still produce PRE_FP1 predictions."""
    service = PredictionService(db=upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

    # Zero sessions exist for r2025_1
    assert len(r2025_1.sessions) == 0

    res = service.predict_race_stage(race_id=r2025_1.id, stage="PRE_FP1")
    assert res["race_id"] == r2025_1.id
    assert res["stage"] == "PRE_FP1"
    assert len(res["predictions"]) == 3
    assert res["data_availability"]["fp1"] is False
    assert res["data_availability"]["qualifying"] is False


def test_leakage_2_no_current_race_result_impact(upcoming_race_db):
    """Test 2: Adding a current/future race result must NOT change PRE_FP1 features or predictions."""
    adapter = FeatureAdapter(upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

    # 1. Baseline PRE_FP1 features before adding any sessions
    feats_before, drivers_before, _ = adapter.build_features_for_race_stage(r2025_1, PredictionStage.PRE_FP1)

    # 2. Add a RACE session with fake results for 2025 Round 1
    race_sess = F1Session(race_id=r2025_1.id, session_type="RACE", session_date=datetime(2025, 3, 16, 5, 0))
    upcoming_race_db.add(race_sess)
    upcoming_race_db.commit()

    ver = upcoming_race_db.query(Driver).filter_by(driver_code="VER").one()
    nor = upcoming_race_db.query(Driver).filter_by(driver_code="NOR").one()
    lec = upcoming_race_db.query(Driver).filter_by(driver_code="LEC").one()

    upcoming_race_db.add_all([
        SessionResult(session_id=race_sess.id, driver_id=nor.id, position=1),
        SessionResult(session_id=race_sess.id, driver_id=ver.id, position=2),
        SessionResult(session_id=race_sess.id, driver_id=lec.id, position=3),
    ])
    upcoming_race_db.commit()

    # 3. Features after adding current race result
    feats_after, drivers_after, _ = adapter.build_features_for_race_stage(r2025_1, PredictionStage.PRE_FP1)

    # PRE_FP1 features MUST be identical
    pd.testing.assert_frame_equal(feats_before, feats_after)


def test_leakage_3_no_weekend_sessions_leakage(upcoming_race_db):
    """Test 3: Adding FP1/FP2/FP3/Qualifying sessions must NOT change PRE_FP1 features."""
    adapter = FeatureAdapter(upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

    feats_pre, _, _ = adapter.build_features_for_race_stage(r2025_1, PredictionStage.PRE_FP1)

    # Add FP1 and QUALIFYING sessions
    fp1 = F1Session(race_id=r2025_1.id, session_type="FP1", session_date=datetime(2025, 3, 14, 1, 30))
    quali = F1Session(race_id=r2025_1.id, session_type="QUALIFYING", session_date=datetime(2025, 3, 15, 5, 0))
    upcoming_race_db.add_all([fp1, quali])
    upcoming_race_db.commit()

    nor = upcoming_race_db.query(Driver).filter_by(driver_code="NOR").one()
    upcoming_race_db.add(SessionResult(session_id=fp1.id, driver_id=nor.id, position=1, lap_time=78.5))
    upcoming_race_db.add(SessionResult(session_id=quali.id, driver_id=nor.id, position=1, lap_time=77.2))
    upcoming_race_db.commit()

    feats_post_sessions, _, _ = adapter.build_features_for_race_stage(r2025_1, PredictionStage.PRE_FP1)

    pd.testing.assert_frame_equal(feats_pre, feats_post_sessions)


def test_leakage_4_historical_cutoff(upcoming_race_db):
    """Test 4: Races occurring after target race MUST NOT contribute to features."""
    adapter = FeatureAdapter(upcoming_race_db)
    r2024_1 = upcoming_race_db.query(Race).filter_by(season=2024, round=1).one()

    # Predict for 2024 Round 1. 2024 Round 2 results exist in DB, but round 2 occurs AFTER round 1!
    feats_r1, _, _ = adapter.build_features_for_race_stage(r2024_1, PredictionStage.PRE_FP1)

    # Verify that driver_season_points for Round 1 is 0.0 (Round 2 result ignored)
    assert (feats_r1["driver_season_points"] == 0.0).all()


def test_leakage_5_circuit_historical_cutoff(upcoming_race_db):
    """Test 5: Only previous completed editions of the target circuit contribute to circuit history."""
    adapter = FeatureAdapter(upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one() # Australian GP (Albert Park)

    # In upcoming_race_db, Albert Park has 0 prior editions (2024 races were Bahrain & Saudi)
    feats, _, _ = adapter.build_features_for_race_stage(r2025_1, PredictionStage.PRE_FP1)
    assert (feats["driver_circuit_starts"] == 0).all()
    assert feats["driver_circuit_avg_finish"].isna().all()


def test_leakage_6_deterministic_output(upcoming_race_db):
    """Test 6: Given same DB state and target race, PRE_FP1 features are 100% deterministic."""
    adapter = FeatureAdapter(upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

    feats1, _, _ = adapter.build_features_for_race_stage(r2025_1, PredictionStage.PRE_FP1)
    feats2, _, _ = adapter.build_features_for_race_stage(r2025_1, PredictionStage.PRE_FP1)

    pd.testing.assert_frame_equal(feats1, feats2)


def test_leakage_7_driver_coverage(upcoming_race_db):
    """Test 7: Every active/resolvable driver for the target race receives a feature row and prediction."""
    service = PredictionService(db=upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

    res = service.predict_race_stage(race_id=r2025_1.id, stage="PRE_FP1")
    predicted_codes = {p["driver_code"] for p in res["predictions"]}
    assert predicted_codes == {"NOR", "VER", "LEC"}


def test_leakage_8_probability_validity(upcoming_race_db):
    """Test 8: Model output probabilities and predicted finish positions are valid and finite."""
    service = PredictionService(db=upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

    res = service.predict_race_stage(race_id=r2025_1.id, stage="PRE_FP1")

    total_share = sum(p["race_share_probability"] for p in res["predictions"])
    assert pytest.approx(total_share, abs=1e-3) == 1.0

    for pred in res["predictions"]:
        assert 0.0 <= pred["raw_win_probability"] <= 1.0
        assert 0.0 <= pred["race_share_probability"] <= 1.0
        assert 0.0 <= pred["podium_probability"] <= 1.0
        assert 0.0 <= pred["top5_probability"] <= 1.0
        assert np.isfinite(pred["predicted_finish_position"])
        assert pred["predicted_finish_position"] >= 1.0


def test_upcoming_race_api_endpoint(upcoming_race_db):
    """Phase 10: API integration test for GET /api/races/{race_id}/predictions?stage=PRE_FP1."""
    def _override_get_db():
        try:
            yield upcoming_race_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as client:
            r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

            # Test GET /api/races/{race_id}/predictions?stage=PRE_FP1
            response = client.get(f"/api/races/{r2025_1.id}/predictions?stage=PRE_FP1")
            assert response.status_code == 200
            data = response.json()

            assert data["race_id"] == r2025_1.id
            assert data["stage"] == "PRE_FP1"
            assert len(data["predictions"]) == 3
            assert data["data_availability"]["historical_form"] is True

            # Test GET /api/races/{race_id}/predictions/PRE_FP1
            res_path = client.get(f"/api/races/{r2025_1.id}/predictions/PRE_FP1")
            assert res_path.status_code == 200
            assert res_path.json()["stage"] == "PRE_FP1"

    finally:
        app.dependency_overrides.clear()


def test_later_stages_not_broken(upcoming_race_db):
    """Phase 11: Verify that POST_FP1, POST_FP2, POST_FP3, POST_QUALIFYING stages still work as expected."""
    service = PredictionService(db=upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

    # Add FP1 and FP2 sessions
    fp1 = F1Session(race_id=r2025_1.id, session_type="FP1", session_date=datetime(2025, 3, 14, 1, 30))
    fp2 = F1Session(race_id=r2025_1.id, session_type="FP2", session_date=datetime(2025, 3, 14, 5, 0))
    upcoming_race_db.add_all([fp1, fp2])
    upcoming_race_db.commit()

    nor = upcoming_race_db.query(Driver).filter_by(driver_code="NOR").one()
    upcoming_race_db.add_all([
        SessionResult(session_id=fp1.id, driver_id=nor.id, position=1, lap_time=78.5),
        SessionResult(session_id=fp2.id, driver_id=nor.id, position=2, lap_time=78.1),
    ])
    upcoming_race_db.commit()

    # POST_FP1: FP1 is available, FP2 is not yet available for model inference
    res_fp1 = service.predict_race_stage(race_id=r2025_1.id, stage="POST_FP1")
    assert res_fp1["stage"] == "POST_FP1"
    assert res_fp1["data_availability"]["fp1"] is True
    assert res_fp1["data_availability"]["fp2"] is False

    # POST_FP2: Both FP1 and FP2 are available
    res_fp2 = service.predict_race_stage(race_id=r2025_1.id, stage="POST_FP2")
    assert res_fp2["stage"] == "POST_FP2"
    assert res_fp2["data_availability"]["fp1"] is True
    assert res_fp2["data_availability"]["fp2"] is True

    # POST_QUALIFYING
    res_q = service.predict_race_stage(race_id=r2025_1.id, stage="POST_QUALIFYING")
    assert res_q["stage"] == "POST_QUALIFYING"


def test_driver_specific_feature_differentiation(upcoming_race_db):
    """Regression test: Ensures PRE_FP1 feature vectors and predictions are driver-specific when historical data differs."""
    adapter = FeatureAdapter(upcoming_race_db)
    service = PredictionService(db=upcoming_race_db)
    r2025_1 = upcoming_race_db.query(Race).filter_by(season=2025, round=1).one()

    # 1. Extract feature matrix
    feats_df, drivers_info, data_avail = adapter.build_features_for_race_stage(r2025_1, PredictionStage.PRE_FP1)
    assert data_avail["fp1"] is False
    assert data_avail["qualifying"] is False

    # Check distinct feature values
    nor_idx = next(i for i, d in enumerate(drivers_info) if d["driver_code"] == "NOR")
    ver_idx = next(i for i, d in enumerate(drivers_info) if d["driver_code"] == "VER")
    lec_idx = next(i for i, d in enumerate(drivers_info) if d["driver_code"] == "LEC")

    nor_avg = feats_df.iloc[nor_idx]["driver_recent_avg_finish"]
    ver_avg = feats_df.iloc[ver_idx]["driver_recent_avg_finish"]
    lec_avg = feats_df.iloc[lec_idx]["driver_recent_avg_finish"]

    # Feature values MUST NOT be identical across different drivers (VER vs NOR, VER vs LEC)
    assert ver_avg != nor_avg
    assert ver_avg != lec_avg

    # 2. Run prediction service
    res = service.predict_race_stage(race_id=r2025_1.id, stage="PRE_FP1")
    preds = {p["driver_code"]: p for p in res["predictions"]}

    # Predictions MUST NOT be identical across different drivers
    assert preds["VER"]["race_share_probability"] != preds["NOR"]["race_share_probability"]
    assert preds["VER"]["race_share_probability"] != preds["LEC"]["race_share_probability"]
    assert preds["VER"]["predicted_finish_position"] != preds["NOR"]["predicted_finish_position"]

