import logging
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from sqlalchemy.orm import Session as DBSession

from app.models import Driver, Race, Session as F1Session, SessionResult
from app.services.f1_data.fastf1_service import FastF1DataError, FastF1Service

logger = logging.getLogger(__name__)

FASTF1_SESSION_MAPPING: Dict[str, str] = {
    "FP1": "FP1",
    "FP2": "FP2",
    "FP3": "FP3",
    "QUALIFYING": "Q",
}


class FastF1Enricher:
    """Enriches database with real FastF1 session timings (FP1, FP2, FP3, Qualifying)."""

    def __init__(self, db: DBSession, service: Optional[FastF1Service] = None):
        self.db = db
        self.service = service or FastF1Service()

    def _match_driver(self, abbreviation: str, full_name: str) -> Optional[Driver]:
        """Match FastF1 driver to PostgreSQL Driver entity using code or name."""
        if abbreviation:
            d = self.db.query(Driver).filter(Driver.driver_code == abbreviation.strip().upper()).first()
            if d:
                return d

        if full_name:
            d = self.db.query(Driver).filter(Driver.name.ilike(full_name.strip())).first()
            if d:
                return d

            last_name = full_name.strip().split()[-1]
            if len(last_name) > 2:
                d = self.db.query(Driver).filter(Driver.name.ilike(f"%{last_name}%")).first()
                if d:
                    return d

        return None

    def enrich_race_session(
        self,
        race: Race,
        session_type: str,
    ) -> int:
        """
        Fetch real session timings from FastF1 for a single race & session,
        and perform an idempotent upsert into session_results.
        """
        if session_type not in FASTF1_SESSION_MAPPING:
            logger.warning("Unsupported enrichment session type: %s", session_type)
            return 0

        fastf1_code = FASTF1_SESSION_MAPPING[session_type]

        # 1. Get or create F1Session in DB
        db_session = (
            self.db.query(F1Session)
            .filter(F1Session.race_id == race.id, F1Session.session_type == session_type)
            .first()
        )
        if not db_session:
            db_session = F1Session(race_id=race.id, session_type=session_type)
            self.db.add(db_session)
            self.db.flush()

        # 2. Fetch FastF1 session
        try:
            ff1_sess = self.service.get_session(
                year=race.season,
                grand_prix=race.round,
                session_type=fastf1_code,
            )
            self.service.load_session(ff1_sess, laps=True, telemetry=False, weather=False)
        except Exception as e:
            logger.warning(
                "FastF1 data unavailable for race %d (season %d, round %d), session %s: %s",
                race.id, race.season, race.round, session_type, e
            )
            return 0

        if not hasattr(ff1_sess, "results") or ff1_sess.results is None or ff1_sess.results.empty:
            logger.warning("FastF1 results empty for race %d session %s", race.id, session_type)
            return 0

        # Extract lap timings & driver results
        extracted_rows = []
        for idx, row in ff1_sess.results.iterrows():
            abbreviation = str(row.get("Abbreviation") or "").strip()
            full_name = str(row.get("FullName") or "").strip()
            raw_pos = row.get("Position")
            
            position = int(raw_pos) if pd.notna(raw_pos) and str(raw_pos).replace('.', '', 1).isdigit() else None
            
            time_val = row.get("Time")
            lap_time_sec = time_val.total_seconds() if hasattr(time_val, "total_seconds") and pd.notna(time_val) else None

            # For Qualifying sessions, extract best lap from Q3, Q2, Q1 if Time is NaT
            if session_type == "QUALIFYING" and lap_time_sec is None:
                for q_col in ["Q3", "Q2", "Q1"]:
                    q_val = row.get(q_col)
                    if hasattr(q_val, "total_seconds") and pd.notna(q_val):
                        lap_time_sec = q_val.total_seconds()
                        break

            laps_count = int(row.get("Laps")) if "Laps" in row and pd.notna(row.get("Laps")) else None

            s1_sec, s2_sec, s3_sec, compound = None, None, None, None

            # Look up fastest lap details if available
            if hasattr(ff1_sess, "laps") and ff1_sess.laps is not None and not ff1_sess.laps.empty:
                try:
                    driver_laps = ff1_sess.laps[ff1_sess.laps["Driver"] == abbreviation]
                    if not driver_laps.empty:
                        fastest_lap = driver_laps.pick_fastest()
                        if fastest_lap is not None and not fastest_lap.empty:
                            s1 = fastest_lap.get("Sector1Time")
                            s2 = fastest_lap.get("Sector2Time")
                            s3 = fastest_lap.get("Sector3Time")

                            s1_sec = s1.total_seconds() if hasattr(s1, "total_seconds") else None
                            s2_sec = s2.total_seconds() if hasattr(s2, "total_seconds") else None
                            s3_sec = s3.total_seconds() if hasattr(s3, "total_seconds") else None
                            compound = str(fastest_lap.get("Compound")) if fastest_lap.get("Compound") else None

                            if lap_time_sec is None:
                                lap_t = fastest_lap.get("LapTime")
                                lap_time_sec = lap_t.total_seconds() if hasattr(lap_t, "total_seconds") else None
                except Exception as ex:
                    logger.debug("Fastest lap lookup error for driver %s: %s", abbreviation, ex)

            extracted_rows.append({
                "abbreviation": abbreviation,
                "full_name": full_name,
                "position": position,
                "lap_time": lap_time_sec,
                "sector_1": s1_sec,
                "sector_2": s2_sec,
                "sector_3": s3_sec,
                "tyre": compound,
                "laps": laps_count,
            })

        # Calculate session positions by fastest lap time if Position was missing
        valid_lap_rows = [r for r in extracted_rows if r["lap_time"] is not None]
        valid_lap_rows.sort(key=lambda r: r["lap_time"])
        for rank, r in enumerate(valid_lap_rows, start=1):
            if r["position"] is None:
                r["position"] = rank

        # Upsert into session_results table
        stored_count = 0
        for r_data in extracted_rows:
            driver = self._match_driver(r_data["abbreviation"], r_data["full_name"])
            if not driver:
                logger.debug("Could not match FastF1 driver %s (%s) to DB", r_data["abbreviation"], r_data["full_name"])
                continue

            session_result = (
                self.db.query(SessionResult)
                .filter(
                    SessionResult.session_id == db_session.id,
                    SessionResult.driver_id == driver.id,
                )
                .first()
            )

            if session_result:
                session_result.position = r_data["position"]
                session_result.lap_time = r_data["lap_time"]
                session_result.sector_1 = r_data["sector_1"]
                session_result.sector_2 = r_data["sector_2"]
                session_result.sector_3 = r_data["sector_3"]
                session_result.tyre = r_data["tyre"]
                session_result.laps = r_data["laps"]
            else:
                session_result = SessionResult(
                    session_id=db_session.id,
                    driver_id=driver.id,
                    position=r_data["position"],
                    lap_time=r_data["lap_time"],
                    sector_1=r_data["sector_1"],
                    sector_2=r_data["sector_2"],
                    sector_3=r_data["sector_3"],
                    tyre=r_data["tyre"],
                    laps=r_data["laps"],
                )
                self.db.add(session_result)

            stored_count += 1

        self.db.commit()
        logger.info("Enriched race %d session %s with %d driver results", race.id, session_type, stored_count)
        return stored_count

    def enrich_season(self, season: int, sessions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Orchestrate FastF1 enrichment for all races in a season."""
        target_sessions = sessions or ["FP1", "FP2", "FP3", "QUALIFYING"]
        races = self.db.query(Race).filter(Race.season == season).order_by(Race.round.asc()).all()

        total_sessions = 0
        total_results = 0

        for race in races:
            for stype in target_sessions:
                count = self.enrich_race_session(race, stype)
                if count > 0:
                    total_sessions += 1
                    total_results += count

        return {
            "season": season,
            "races_processed": len(races),
            "sessions_enriched": total_sessions,
            "session_results_stored": total_results,
        }
