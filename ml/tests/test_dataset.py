from datetime import date, datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Driver, Race, Session as F1Session, SessionResult, Team
from ml.config import TARGET_FINISH_POSITION, TARGET_WIN
from ml.datasets.build_dataset import build_ml_dataset
from ml.stages import STAGE_ORDER, PredictionStage
from ml.validation.leakage_checks import validate_dataset_no_leakage


@pytest.fixture
def dataset_test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionFactory()

    mclaren = Team(name="McLaren", constructor_code="mclaren", country="UK")
    session.add(mclaren)
    session.commit()

    norris = Driver(driver_code="NOR", name="Lando Norris", country="UK", team_id=mclaren.id)
    session.add(norris)
    session.commit()

    race = Race(
        season=2025,
        round=1,
        race_name="Australian GP",
        circuit="Albert Park",
        country="Australia",
        race_date=date(2025, 3, 16),
    )
    session.add(race)
    session.commit()

    fp1 = F1Session(race_id=race.id, session_type="FP1", session_date=datetime(2025, 3, 14, 1, 30))
    fp2 = F1Session(race_id=race.id, session_type="FP2", session_date=datetime(2025, 3, 14, 5, 0))
    quali = F1Session(race_id=race.id, session_type="QUALIFYING", session_date=datetime(2025, 3, 15, 5, 0))
    race_sess = F1Session(race_id=race.id, session_type="RACE", session_date=datetime(2025, 3, 16, 4, 0))
    session.add_all([fp1, fp2, quali, race_sess])
    session.commit()

    session.add(SessionResult(session_id=fp1.id, driver_id=norris.id, position=2, lap_time=81.0))
    session.add(SessionResult(session_id=fp2.id, driver_id=norris.id, position=1, lap_time=80.5))
    session.add(SessionResult(session_id=quali.id, driver_id=norris.id, position=1, lap_time=79.5))
    session.add(SessionResult(session_id=race_sess.id, driver_id=norris.id, position=1, lap_time=79.0, laps=58))
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_build_ml_dataset(dataset_test_db, tmp_path):
    out_csv = tmp_path / "test_dataset.csv"
    df = build_ml_dataset(db=dataset_test_db, output_path=out_csv, stages=[PredictionStage.PRE_FP1, PredictionStage.POST_QUALIFYING])

    assert not df.empty
    assert len(df) == 2 # 1 driver * 2 stages
    assert TARGET_FINISH_POSITION in df.columns
    assert TARGET_WIN in df.columns

    norris_pre_fp1 = df[df["prediction_stage"] == "PRE_FP1"].iloc[0]
    assert norris_pre_fp1[TARGET_FINISH_POSITION] == 1.0
    assert norris_pre_fp1[TARGET_WIN] == 1

    # Leakage check test
    is_valid, violations = validate_dataset_no_leakage(df)
    assert is_valid
    assert len(violations) == 0
