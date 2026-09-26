import logging
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models import Driver, Race, Session as F1Session, SessionResult, Team
from ml.datasets.build_dataset import load_historical_race_results
from ml.features.feature_pipeline import FeaturePipeline
from ml.features.metadata import FEATURE_METADATA
from ml.stages import PredictionStage, is_stage_at_or_after

logger = logging.getLogger(__name__)


class FeatureAdapter:
    """Adapts database entities and FeaturePipeline into model feature matrices for prediction."""

    def __init__(self, db: DBSession):
        self.db = db
        self.pipeline = FeaturePipeline()

    def build_features_for_race_stage(
        self,
        race: Race,
        stage: PredictionStage,
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]], Dict[str, bool]]:
        """
        Extract feature matrix, driver roster metadata, and data availability flags for a race and stage.
        """
        # Ensure stage is PredictionStage enum
        if isinstance(stage, str):
            stage = PredictionStage(stage.upper())

        # Load historical race results prior to race
        historical_df = load_historical_race_results(self.db)

        # Load current race session results
        sess_stmt = (
            select(
                F1Session.session_type,
                SessionResult.driver_id,
                SessionResult.position,
                SessionResult.lap_time,
                Driver.driver_code,
                Driver.name.label("driver_name"),
                Driver.team_id,
                Team.name.label("team_name"),
            )
            .join(SessionResult, SessionResult.session_id == F1Session.id)
            .join(Driver, Driver.id == SessionResult.driver_id)
            .outerjoin(Team, Team.id == Driver.team_id)
            .where(F1Session.race_id == race.id)
        )

        weekend_rows = self.db.execute(sess_stmt).all()
        weekend_df = (
            pd.DataFrame(
                weekend_rows,
                columns=["session_type", "driver_id", "position", "lap_time", "driver_code", "driver_name", "team_id", "team_name"],
            )
            if weekend_rows
            else pd.DataFrame(columns=["session_type", "driver_id", "position", "lap_time", "driver_code", "driver_name", "team_id", "team_name"])
        )

        # Build comprehensive driver roster for the race
        roster_map: Dict[int, Dict[str, Any]] = {}
        if weekend_rows:
            for r in weekend_rows:
                d_id = int(r.driver_id)
                if d_id not in roster_map:
                    roster_map[d_id] = {
                        "driver_id": d_id,
                        "driver_code": str(r.driver_code),
                        "driver_name": str(r.driver_name),
                        "team_id": int(r.team_id) if pd.notna(r.team_id) else None,
                        "team_name": str(r.team_name) if pd.notna(r.team_name) else None,
                    }

        # Enrich roster with prior season drivers or active team drivers in DB
        prior_season_driver_stmt = (
            select(
                Driver.id.label("driver_id"),
                Driver.driver_code,
                Driver.name.label("driver_name"),
                Driver.team_id,
                Team.name.label("team_name"),
            )
            .join(SessionResult, SessionResult.driver_id == Driver.id)
            .join(F1Session, F1Session.id == SessionResult.session_id)
            .join(Race, Race.id == F1Session.race_id)
            .outerjoin(Team, Team.id == Driver.team_id)
            .where(Race.season == race.season, Race.round < race.round)
            .distinct()
        )
        season_drivers = self.db.execute(prior_season_driver_stmt).all()

        if season_drivers:
            for r in season_drivers:
                d_id = int(r.driver_id)
                if d_id not in roster_map:
                    roster_map[d_id] = {
                        "driver_id": d_id,
                        "driver_code": str(r.driver_code),
                        "driver_name": str(r.driver_name),
                        "team_id": int(r.team_id) if pd.notna(r.team_id) else None,
                        "team_name": str(r.team_name) if pd.notna(r.team_name) else None,
                    }
        else:
            drivers_db = self.db.scalars(
                select(Driver).where(Driver.team_id.isnot(None))
            ).all()
            if not drivers_db:
                drivers_db = self.db.scalars(select(Driver)).all()

            for d in drivers_db:
                d_id = int(d.id)
                if d_id not in roster_map:
                    roster_map[d_id] = {
                        "driver_id": d_id,
                        "driver_code": str(d.driver_code),
                        "driver_name": str(d.name),
                        "team_id": int(d.team_id) if d.team_id is not None else None,
                        "team_name": str(d.team.name) if d.team else None,
                    }

        driver_roster = list(roster_map.values())

        feature_cols = list(FEATURE_METADATA.keys())
        feature_rows = []
        drivers_info = []

        # Check stage-aware data availability in current weekend data
        has_fp1 = not weekend_df[weekend_df["session_type"] == "FP1"].empty if not weekend_df.empty else False
        has_fp2 = not weekend_df[weekend_df["session_type"] == "FP2"].empty if not weekend_df.empty else False
        has_fp3 = not weekend_df[weekend_df["session_type"] == "FP3"].empty if not weekend_df.empty else False
        has_quali = not weekend_df[weekend_df["session_type"] == "QUALIFYING"].empty if not weekend_df.empty else False

        data_availability = {
            "historical_form": not historical_df.empty,
            "fp1": has_fp1 and is_stage_at_or_after(stage, PredictionStage.POST_FP1),
            "fp2": has_fp2 and is_stage_at_or_after(stage, PredictionStage.POST_FP2),
            "fp3": has_fp3 and is_stage_at_or_after(stage, PredictionStage.POST_FP3),
            "qualifying": has_quali and is_stage_at_or_after(stage, PredictionStage.POST_QUALIFYING),
        }

        for d_info in driver_roster:
            d_id = int(d_info["driver_id"])
            raw_team_id = d_info.get("team_id")
            t_id = int(raw_team_id) if (raw_team_id is not None and pd.notna(raw_team_id)) else None

            feats = self.pipeline.extract_features_for_row(
                driver_id=d_id,
                team_id=t_id,
                season=race.season,
                round_num=race.round,
                circuit_name=race.circuit,
                stage=stage,
                current_weekend_results_df=weekend_df,
                historical_race_results_df=historical_df,
            )

            feature_rows.append(feats)
            drivers_info.append({
                "driver_id": d_id,
                "driver_code": str(d_info["driver_code"]),
                "driver_name": str(d_info["driver_name"]),
                "team_id": t_id,
                "team_name": str(d_info["team_name"]) if pd.notna(d_info.get("team_name")) else None,
            })

        features_df = pd.DataFrame(feature_rows) if feature_rows else pd.DataFrame(columns=feature_cols)

        # Ensure all expected feature columns exist
        for col in feature_cols:
            if col not in features_df.columns:
                features_df[col] = np.nan

        # Sort columns to match exact FEATURE_METADATA ordering
        features_df = features_df[feature_cols]

        return features_df, drivers_info, data_availability
