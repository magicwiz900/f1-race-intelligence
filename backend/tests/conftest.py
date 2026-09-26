from datetime import date, datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.main import app
from app.models import Base, Driver, Race, Session as F1Session, SessionResult, Team


@pytest.fixture(scope="function")
def api_test_db():
    """Isolated in-memory SQLite database session for API unit tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionFactory()

    # Seed initial test data
    mclaren = Team(name="McLaren", constructor_code="mclaren", country="United Kingdom")
    session.add(mclaren)
    session.commit()

    norris = Driver(driver_code="NOR", name="Lando Norris", country="United Kingdom", team_id=mclaren.id)
    session.add(norris)
    session.commit()

    race_2025_1 = Race(
        season=2025,
        round=1,
        race_name="Australian Grand Prix",
        circuit="Albert Park Circuit",
        country="Australia",
        race_date=date(2025, 3, 16),
    )
    session.add(race_2025_1)
    session.commit()

    fp1 = F1Session(race_id=race_2025_1.id, session_type="FP1", session_date=datetime(2025, 3, 14, 1, 30))
    race_sess = F1Session(race_id=race_2025_1.id, session_type="RACE", session_date=datetime(2025, 3, 16, 4, 0))
    session.add_all([fp1, race_sess])
    session.commit()

    res = SessionResult(
        session_id=race_sess.id,
        driver_id=norris.id,
        position=1,
        lap_time=79.812,
        laps=58,
    )
    session.add(res)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(api_test_db):
    def _override_get_db():
        try:
            yield api_test_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
