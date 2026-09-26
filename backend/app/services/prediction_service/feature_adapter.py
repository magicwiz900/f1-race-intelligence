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
from ml.stages import PredictionStage

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

        if weekend_rows:
            weekend_df = pd.DataFrame(
                weekend_rows,
                columns=["session_type", "driver_id", "position", "lap_time", "driver_code", "driver_name", "team_id", "team_name"],
            )
            driver_roster = (
                weekend_df[["driver_id", "driver_code", "driver_name", "team_id", "team_name"]]
                .drop_duplicates(subset=["driver_id"])
                .to_dict(orient="records")
            )
        else:
            # Fallback to querying drivers directly from database
            weekend_df = pd.DataFrame(columns=["session_type", "driver_id", "position", "lap_time", "driver_code", "driver_name", "team_id", "team_name"])
            drivers_db = self.db.scalars(select(Driver)).all()
            driver_roster = []
            for d in drivers_db:
                driver_roster.append({
                    "driver_id": d.id,
                    "driver_code": d.driver_code,
                    "driver_name": d.name,
                    "team_id": d.team_id,
                    "team_name": d.team.name if d.team else None,
                })

        feature_cols = list(FEATURE_METADATA.keys())
        feature_rows = []
        drivers_info = []

        # Check data availability in current weekend data
        has_fp1 = not weekend_df[weekend_df["session_type"] == "FP1"].empty if not weekend_df.empty else False
        has_fp2 = not weekend_df[weekend_df["session_type"] == "FP2"].empty if not weekend_df.empty else False
        has_fp3 = not weekend_df[weekend_df["session_type"] == "FP3"].empty if not weekend_df.empty else False
        has_quali = not weekend_df[weekend_df["session_type"] == "QUALIFYING"].empty if not weekend_df.empty else False

        data_availability = {
            "historical_form": True,
            "fp1": has_fp1,
            "fp2": has_fp2,
            "fp3": has_fp3,
            "qualifying": has_quali,
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
