from datetime import date, datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Driver, Prediction, Race, Session as F1Session, SessionResult, Team


@pytest.fixture(scope="function")
def test_db_session():
    """Fixture providing an isolated in-memory SQLite database session for unit tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_table_creation(test_db_session: Session):
    """Verify metadata and all 6 tables are created in test database."""
    tables = Base.metadata.tables.keys()
    assert "teams" in tables
    assert "drivers" in tables
    assert "races" in tables
    assert "sessions" in tables
    assert "session_results" in tables
    assert "predictions" in tables


def test_team_driver_relationship(test_db_session: Session):
    """Verify Team and Driver relationship and cascade."""
    ferrari = Team(name="Ferrari", constructor_code="ferrari", country="Italy")
    test_db_session.add(ferrari)
    test_db_session.commit()

    lec = Driver(driver_code="LEC", name="Charles Leclerc", country="Monaco", team_id=ferrari.id)
    ham = Driver(driver_code="HAM", name="Lewis Hamilton", country="United Kingdom", team_id=ferrari.id)
    test_db_session.add_all([lec, ham])
    test_db_session.commit()

    # Query back
    queried_team = test_db_session.query(Team).filter_by(name="Ferrari").first()
    assert queried_team is not None
    assert len(queried_team.drivers) == 2
    driver_codes = [d.driver_code for d in queried_team.drivers]
    assert "LEC" in driver_codes
    assert "HAM" in driver_codes


def test_race_session_relationship(test_db_session: Session):
    """Verify Race and Session relationship."""
    monaco_gp = Race(
        season=2026,
        round=8,
        race_name="Monaco Grand Prix",
        circuit="Circuit de Monaco",
        country="Monaco",
        race_date=date(2026, 5, 24),
    )
    test_db_session.add(monaco_gp)
    test_db_session.commit()

    fp1 = F1Session(race_id=monaco_gp.id, session_type="FP1", session_date=datetime(2026, 5, 22, 11, 30))
    quali = F1Session(race_id=monaco_gp.id, session_type="QUALIFYING", session_date=datetime(2026, 5, 23, 14, 0))
    race_sess = F1Session(race_id=monaco_gp.id, session_type="RACE", session_date=datetime(2026, 5, 24, 13, 0))
    
    test_db_session.add_all([fp1, quali, race_sess])
    test_db_session.commit()

    queried_race = test_db_session.query(Race).filter_by(season=2026, round=8).first()
    assert queried_race is not None
    assert len(queried_race.sessions) == 3
    session_types = [s.session_type for s in queried_race.sessions]
    assert "FP1" in session_types
    assert "QUALIFYING" in session_types
    assert "RACE" in session_types


def test_session_result_references(test_db_session: Session):
    """Verify SessionResult correctly references Session and Driver."""
    team = Team(name="Red Bull", constructor_code="red_bull", country="Austria")
    test_db_session.add(team)
    test_db_session.commit()

    ver = Driver(driver_code="VER", name="Max Verstappen", country="Netherlands", team_id=team.id)
    test_db_session.add(ver)
    test_db_session.commit()

    race = Race(
        season=2026,
        round=1,
        race_name="Bahrain Grand Prix",
        circuit="Bahrain International Circuit",
        country="Bahrain",
        race_date=date(2026, 3, 2),
    )
    test_db_session.add(race)
    test_db_session.commit()

    session = F1Session(race_id=race.id, session_type="QUALIFYING")
    test_db_session.add(session)
    test_db_session.commit()

    result = SessionResult(
        session_id=session.id,
        driver_id=ver.id,
        position=1,
        lap_time=89.123,
        sector_1=28.1,
        sector_2=38.4,
        sector_3=22.623,
        tyre="SOFT",
        laps=12,
    )
    test_db_session.add(result)
    test_db_session.commit()

    queried_res = test_db_session.query(SessionResult).first()
    assert queried_res is not None
    assert queried_res.driver.driver_code == "VER"
    assert queried_res.session.session_type == "QUALIFYING"
    assert queried_res.position == 1
    assert queried_res.lap_time == 89.123


def test_prediction_references(test_db_session: Session):
    """Verify Prediction correctly references Race and Driver across prediction stages."""
    mclaren = Team(name="McLaren", constructor_code="mclaren", country="United Kingdom")
    test_db_session.add(mclaren)
    test_db_session.commit()

    nor = Driver(driver_code="NOR", name="Lando Norris", country="United Kingdom", team_id=mclaren.id)
    test_db_session.add(nor)
    test_db_session.commit()

    race = Race(
        season=2026,
        round=3,
        race_name="Australian Grand Prix",
        circuit="Albert Park Circuit",
        country="Australia",
        race_date=date(2026, 3, 16),
    )
    test_db_session.add(race)
    test_db_session.commit()

    pred_post_fp2 = Prediction(
        race_id=race.id,
        driver_id=nor.id,
        prediction_stage="POST_FP2",
        predicted_position=2,
        win_probability=0.25,
        podium_probability=0.70,
        top5_probability=0.92,
        model_version="v1.0.0",
    )
    test_db_session.add(pred_post_fp2)
    test_db_session.commit()

    queried_pred = test_db_session.query(Prediction).filter_by(prediction_stage="POST_FP2").first()
    assert queried_pred is not None
    assert queried_pred.driver.driver_code == "NOR"
    assert queried_pred.race.race_name == "Australian Grand Prix"
    assert queried_pred.win_probability == 0.25
    assert queried_pred.podium_probability == 0.70


def test_uniqueness_constraints(test_db_session: Session):
    """Verify unique constraints behave correctly."""
    team1 = Team(name="Mercedes", constructor_code="mercedes")
    test_db_session.add(team1)
    test_db_session.commit()

    # Duplicate team name should raise IntegrityError
    team2 = Team(name="Mercedes", constructor_code="merc_dup")
    test_db_session.add(team2)
    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()

    # Unique race season + round constraint
    race1 = Race(season=2026, round=5, race_name="GP 1", circuit="C1", race_date=date(2026, 4, 1))
    test_db_session.add(race1)
    test_db_session.commit()

    race2 = Race(season=2026, round=5, race_name="GP 2", circuit="C2", race_date=date(2026, 4, 2))
    test_db_session.add(race2)
    with pytest.raises(IntegrityError):
        test_db_session.commit()
