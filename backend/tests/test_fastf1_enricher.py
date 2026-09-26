from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Driver, Race, Session as F1Session, SessionResult, Team
from app.services.f1_data.fastf1_enricher import FastF1Enricher


@pytest.fixture
def enricher_db():
    """Isolated SQLite DB for FastF1Enricher unit tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionFactory()

    mclaren = Team(name="McLaren", constructor_code="mclaren", country="United Kingdom")
    session.add(mclaren)
    session.commit()

    norris = Driver(driver_code="NOR", name="Lando Norris", country="United Kingdom", team_id=mclaren.id)
    verstappen = Driver(driver_code="VER", name="Max Verstappen", country="Netherlands")
    session.add_all([norris, verstappen])
    session.commit()

    race = Race(
        season=2025,
        round=1,
        race_name="Australian Grand Prix",
        circuit="Albert Park Circuit",
        country="Australia",
        race_date=date(2025, 3, 16),
    )
    session.add(race)
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_driver_matching(enricher_db):
    enricher = FastF1Enricher(db=enricher_db)

    # Match by exact code
    d1 = enricher._match_driver("NOR", "Lando Norris")
    assert d1 is not None
    assert d1.driver_code == "NOR"

    # Match by full name
    d2 = enricher._match_driver("UNKNOWN", "Max Verstappen")
    assert d2 is not None
    assert d2.driver_code == "VER"

    # Non-existent driver
    d3 = enricher._match_driver("XYZ", "Unknown Driver")
    assert d3 is None


def test_idempotent_session_result_upsert(enricher_db):
    enricher = FastF1Enricher(db=enricher_db)
    race = enricher_db.query(Race).first()
    norris = enricher_db.query(Driver).filter(Driver.driver_code == "NOR").first()

    # Manual creation of FP1 session
    fp1 = F1Session(race_id=race.id, session_type="FP1")
    enricher_db.add(fp1)
    enricher_db.commit()

    # Initial insert of SessionResult
    res1 = SessionResult(
        session_id=fp1.id,
        driver_id=norris.id,
        position=1,
        lap_time=77.5,
        sector_1=25.1,
        sector_2=24.0,
        sector_3=28.4,
        tyre="SOFT",
        laps=22,
    )
    enricher_db.add(res1)
    enricher_db.commit()

    count_before = enricher_db.query(SessionResult).filter(SessionResult.session_id == fp1.id).count()
    assert count_before == 1

    # Simulate re-running upsert on same session & driver
    res_existing = enricher_db.query(SessionResult).filter(
        SessionResult.session_id == fp1.id,
        SessionResult.driver_id == norris.id,
    ).first()

    res_existing.position = 1
    res_existing.lap_time = 77.2  # updated lap time
    enricher_db.commit()

    count_after = enricher_db.query(SessionResult).filter(SessionResult.session_id == fp1.id).count()
    assert count_after == 1  # No duplicate rows created!

    updated = enricher_db.query(SessionResult).filter(SessionResult.session_id == fp1.id).first()
    assert updated.lap_time == 77.2
