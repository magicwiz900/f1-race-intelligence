from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession, sessionmaker

from app.models import Base, Driver, Race, Session as F1Session, SessionResult, Team
from app.services.f1_data.importer import F1DataImporter
from app.services.f1_data.jolpica_client import JolpicaClient


@pytest.fixture(scope="function")
def db_session():
    """Isolated in-memory SQLite database session for importer unit tests."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_jolpica_client():
    client = MagicMock(spec=JolpicaClient)
    client.get_constructors.return_value = [
        {"constructorId": "mclaren", "name": "McLaren", "nationality": "British"},
        {"constructorId": "ferrari", "name": "Ferrari", "nationality": "Italian"},
    ]
    client.get_drivers.return_value = [
        {
            "driverId": "norris",
            "code": "NOR",
            "givenName": "Lando",
            "familyName": "Norris",
            "nationality": "British",
        },
        {
            "driverId": "leclerc",
            "code": "LEC",
            "givenName": "Charles",
            "familyName": "Leclerc",
            "nationality": "Monegasque",
        },
    ]
    client.get_races.return_value = [
        {
            "season": "2025",
            "round": "1",
            "raceName": "Australian Grand Prix",
            "Circuit": {
                "circuitName": "Albert Park Circuit",
                "Location": {"country": "Australia"},
            },
            "date": "2025-03-16",
            "time": "04:00:00Z",
            "FirstPractice": {"date": "2025-03-14", "time": "01:30:00Z"},
            "Qualifying": {"date": "2025-03-15", "time": "05:00:00Z"},
        }
    ]
    client.get_all_race_results.return_value = [
        {
            "season": "2025",
            "round": "1",
            "Results": [
                {
                    "position": "1",
                    "laps": "58",
                    "Driver": {
                        "driverId": "norris",
                        "code": "NOR",
                        "givenName": "Lando",
                        "familyName": "Norris",
                        "nationality": "British",
                    },
                    "Constructor": {
                        "constructorId": "mclaren",
                        "name": "McLaren",
                        "nationality": "British",
                    },
                    "FastestLap": {"Time": {"time": "1:19.812"}},
                }
            ],
        }
    ]
    return client


def test_importer_creates_teams_and_drivers(db_session: DBSession, mock_jolpica_client: MagicMock):
    importer = F1DataImporter(db=db_session, client=mock_jolpica_client)
    team_map = importer.import_teams(season=2025)
    driver_map = importer.import_drivers(season=2025, team_map=team_map)

    teams = db_session.query(Team).all()
    assert len(teams) == 2
    team_codes = [t.constructor_code for t in teams]
    assert "mclaren" in team_codes
    assert "ferrari" in team_codes

    drivers = db_session.query(Driver).all()
    assert len(drivers) == 2
    driver_codes = [d.driver_code for d in drivers]
    assert "NOR" in driver_codes
    assert "LEC" in driver_codes


def test_importer_creates_races_and_sessions(db_session: DBSession, mock_jolpica_client: MagicMock):
    importer = F1DataImporter(db=db_session, client=mock_jolpica_client)
    races, count = importer.import_races(season=2025)

    assert count == 1
    assert len(races) == 1
    race = races[0]
    assert race.race_name == "Australian Grand Prix"
    assert race.season == 2025
    assert race.round == 1

    sessions = db_session.query(F1Session).filter_by(race_id=race.id).all()
    assert len(sessions) >= 2
    session_types = [s.session_type for s in sessions]
    assert "FP1" in session_types
    assert "QUALIFYING" in session_types
    assert "RACE" in session_types


def test_importer_links_drivers_to_teams_and_creates_results(db_session: DBSession, mock_jolpica_client: MagicMock):
    importer = F1DataImporter(db=db_session, client=mock_jolpica_client)
    stats = importer.import_season(season=2025)

    assert stats["races"] == 1
    assert stats["session_results"] == 1

    # Check driver team link
    norris = db_session.query(Driver).filter_by(driver_code="NOR").first()
    assert norris is not None
    assert norris.team is not None
    assert norris.team.constructor_code == "mclaren"

    # Check session result
    result = db_session.query(SessionResult).first()
    assert result is not None
    assert result.driver_id == norris.id
    assert result.position == 1
    assert result.laps == 58
    assert result.lap_time == pytest.approx(79.812)
    assert result.sector_1 is None
    assert result.sector_2 is None
    assert result.sector_3 is None
    assert result.tyre is None


def test_import_season_idempotency(db_session: DBSession, mock_jolpica_client: MagicMock):
    """Running importer twice on the same season must NOT duplicate records."""
    importer = F1DataImporter(db=db_session, client=mock_jolpica_client)

    # First run
    stats1 = importer.import_season(season=2025)

    # Second run
    stats2 = importer.import_season(season=2025)

    assert db_session.query(Team).count() == 2
    assert db_session.query(Driver).count() == 2
    assert db_session.query(Race).count() == 1
    assert db_session.query(SessionResult).count() == 1

    norris = db_session.query(Driver).filter_by(driver_code="NOR").first()
    assert norris.name == "Lando Norris"
