import logging
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.models import Driver, Race, Session as F1Session, SessionResult, Team
from app.services.f1_data.jolpica_client import JolpicaClient
from app.services.f1_data.transformers import (
    transform_driver,
    transform_race,
    transform_session_result,
    transform_team,
)

logger = logging.getLogger(__name__)


class F1DataImporter:
    """Importer pipeline for fetching real F1 data from Jolpica and storing in PostgreSQL DB."""

    def __init__(self, db: DBSession, client: Optional[JolpicaClient] = None):
        self.db = db
        self.client = client or JolpicaClient()

    def import_teams(self, season: int) -> Dict[str, Team]:
        """Fetch constructors for season and perform idempotent upsert into teams table."""
        constructors_raw = self.client.get_constructors(season=season)
        team_map: Dict[str, Team] = {}
        imported_count = 0

        for c_data in constructors_raw:
            transformed = transform_team(c_data)
            name = transformed["name"]
            code = transformed["constructor_code"]
            country = transformed["country"]

            if not name:
                continue

            # Check existing team by constructor_code first, then by name
            team = None
            if code:
                team = self.db.query(Team).filter(Team.constructor_code == code).first()
            if not team:
                team = self.db.query(Team).filter(Team.name == name).first()

            if team:
                # Update existing record idempotently
                team.name = name
                if code:
                    team.constructor_code = code
                if country:
                    team.country = country
            else:
                team = Team(
                    name=name,
                    constructor_code=code,
                    country=country,
                )
                self.db.add(team)
                self.db.flush()  # assign id

            if code:
                team_map[code] = team
            team_map[name] = team
            imported_count += 1

        self.db.commit()
        logger.info("Imported/updated %d teams for season %d", imported_count, season)
        return team_map

    def import_drivers(self, season: int, team_map: Optional[Dict[str, Team]] = None) -> Dict[str, Driver]:
        """Fetch drivers for season and perform idempotent upsert into drivers table."""
        drivers_raw = self.client.get_drivers(season=season)
        driver_map: Dict[str, Driver] = {}
        imported_count = 0

        for d_data in drivers_raw:
            transformed = transform_driver(d_data)
            code = transformed["driver_code"]
            name = transformed["name"]
            country = transformed["country"]

            if not code:
                continue

            # Check existing driver by driver_code or name
            driver = self.db.query(Driver).filter(Driver.driver_code == code).first()
            if not driver:
                driver = self.db.query(Driver).filter(Driver.name == name).first()

            if driver:
                driver.driver_code = code
                driver.name = name
                if country:
                    driver.country = country
            else:
                driver = Driver(
                    driver_code=code,
                    name=name,
                    country=country,
                )
                self.db.add(driver)
                self.db.flush()

            driver_map[code] = driver
            driver_map[d_data.get("driverId", "")] = driver
            imported_count += 1

        self.db.commit()
        logger.info("Imported/updated %d drivers for season %d", imported_count, season)
        return driver_map

    def import_races(self, season: int) -> Tuple[List[Race], int]:
        """Fetch race calendar for season and perform idempotent upsert into races table."""
        races_raw = self.client.get_races(season=season)
        races: List[Race] = []
        imported_count = 0

        for r_data in races_raw:
            transformed = transform_race(r_data)
            r_season = transformed["season"]
            r_round = transformed["round"]

            # Lookup by unique constraint (season, round)
            race = self.db.query(Race).filter(
                Race.season == r_season,
                Race.round == r_round,
            ).first()

            if race:
                race.race_name = transformed["race_name"]
                race.circuit = transformed["circuit"]
                race.country = transformed["country"]
                race.race_date = transformed["race_date"]
            else:
                race = Race(
                    season=r_season,
                    round=r_round,
                    race_name=transformed["race_name"],
                    circuit=transformed["circuit"],
                    country=transformed["country"],
                    race_date=transformed["race_date"],
                )
                self.db.add(race)
                self.db.flush()

            # Ensure sessions are created for this race
            self._import_race_sessions(race, transformed["sessions_info"])

            races.append(race)
            imported_count += 1

        self.db.commit()
        logger.info("Imported/updated %d races for season %d", imported_count, season)
        return races, imported_count

    def _import_race_sessions(self, race: Race, sessions_info: List[Dict[str, str]]) -> None:
        """Create/update sessions (FP1, FP2, FP3, QUALIFYING, RACE) for a race."""
        for s_info in sessions_info:
            stype = s_info["session_type"]
            sdate = s_info["session_date"]

            session_obj = self.db.query(F1Session).filter(
                F1Session.race_id == race.id,
                F1Session.session_type == stype,
            ).first()

            if session_obj:
                session_obj.session_date = sdate
            else:
                session_obj = F1Session(
                    race_id=race.id,
                    session_type=stype,
                    session_date=sdate,
                )
                self.db.add(session_obj)

    def import_race_results(
        self,
        season: int,
        team_map: Optional[Dict[str, Team]] = None,
        driver_map: Optional[Dict[str, Driver]] = None,
    ) -> int:
        """Fetch completed race results for season and populate session_results table."""
        all_results_races = self.client.get_all_race_results(season=season)
        results_count = 0

        for race_entry in all_results_races:
            r_season = int(race_entry["season"])
            r_round = int(race_entry["round"])

            race = self.db.query(Race).filter(
                Race.season == r_season,
                Race.round == r_round,
            ).first()

            if not race:
                logger.warning("Race season %d round %d not found in DB when importing results", r_season, r_round)
                continue

            race_session = self.db.query(F1Session).filter(
                F1Session.race_id == race.id,
                F1Session.session_type == "RACE",
            ).first()

            if not race_session:
                race_session = F1Session(race_id=race.id, session_type="RACE")
                self.db.add(race_session)
                self.db.flush()

            raw_results = race_entry.get("Results", [])
            for res in raw_results:
                driver_info = res.get("Driver", {})
                constructor_info = res.get("Constructor", {})

                # Ensure team exists
                c_code = constructor_info.get("constructorId", "")
                c_name = constructor_info.get("name", "")
                team = None
                if team_map and c_code in team_map:
                    team = team_map[c_code]
                elif team_map and c_name in team_map:
                    team = team_map[c_name]
                else:
                    team = self.db.query(Team).filter(
                        (Team.constructor_code == c_code) | (Team.name == c_name)
                    ).first()

                if not team and (c_name or c_code):
                    t_transformed = transform_team(constructor_info)
                    team = Team(
                        name=t_transformed["name"],
                        constructor_code=t_transformed["constructor_code"],
                        country=t_transformed["country"],
                    )
                    self.db.add(team)
                    self.db.flush()
                    if team_map:
                        if c_code:
                            team_map[c_code] = team
                        if c_name:
                            team_map[c_name] = team

                # Ensure driver exists
                d_code = driver_info.get("code", "")
                d_id = driver_info.get("driverId", "")
                driver = None
                if driver_map and d_code in driver_map:
                    driver = driver_map[d_code]
                elif driver_map and d_id in driver_map:
                    driver = driver_map[d_id]
                else:
                    driver = self.db.query(Driver).filter(
                        (Driver.driver_code == d_code) | (Driver.driver_code == d_id.upper()[:10])
                    ).first()

                d_transformed = transform_driver(driver_info, team_id=team.id if team else None)

                if driver:
                    if team and driver.team_id != team.id:
                        driver.team_id = team.id
                else:
                    driver = Driver(
                        driver_code=d_transformed["driver_code"],
                        name=d_transformed["name"],
                        country=d_transformed["country"],
                        team_id=team.id if team else None,
                    )
                    self.db.add(driver)
                    self.db.flush()
                    if driver_map:
                        driver_map[d_transformed["driver_code"]] = driver
                        driver_map[d_id] = driver

                # Transform session result
                res_transformed = transform_session_result(res)

                # Upsert SessionResult
                session_result = self.db.query(SessionResult).filter(
                    SessionResult.session_id == race_session.id,
                    SessionResult.driver_id == driver.id,
                ).first()

                if session_result:
                    session_result.position = res_transformed["position"]
                    session_result.laps = res_transformed["laps"]
                    session_result.lap_time = res_transformed["lap_time"]
                else:
                    session_result = SessionResult(
                        session_id=race_session.id,
                        driver_id=driver.id,
                        position=res_transformed["position"],
                        laps=res_transformed["laps"],
                        lap_time=res_transformed["lap_time"],
                        sector_1=None,
                        sector_2=None,
                        sector_3=None,
                        tyre=None,
                    )
                    self.db.add(session_result)

                results_count += 1

        self.db.commit()
        logger.info("Imported/updated %d session results for season %d", results_count, season)
        return results_count

    def import_season(self, season: int) -> Dict[str, int]:
        """Orchestrate full season ingestion pipeline."""
        logger.info("Fetching season %d...", season)

        team_map = self.import_teams(season=season)
        driver_map = self.import_drivers(season=season, team_map=team_map)
        races, race_count = self.import_races(season=season)
        results_count = self.import_race_results(season=season, team_map=team_map, driver_map=driver_map)

        stats = {
            "season": season,
            "teams": len(team_map),
            "drivers": len(driver_map),
            "races": race_count,
            "session_results": results_count,
        }

        logger.info("Found %d races", race_count)
        logger.info("Imported/updated %d teams", stats["teams"])
        logger.info("Imported/updated %d drivers", stats["drivers"])
        logger.info("Imported/updated %d races", stats["races"])
        logger.info("Ingestion completed successfully")

        return stats
