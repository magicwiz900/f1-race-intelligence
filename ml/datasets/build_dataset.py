import argparse
import logging
from pathlib import Path
import sys
from typing import List, Optional
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.database import SessionLocal
from app.models import Driver, Race, Session as F1Session, SessionResult, Team
from ml.config import DEFAULT_DATASET_CSV, TARGET_FINISH_POSITION, TARGET_PODIUM, TARGET_TOP5, TARGET_WIN
from ml.features.feature_pipeline import FeaturePipeline
from ml.stages import STAGE_ORDER, PredictionStage
from ml.validation.leakage_checks import validate_dataset_no_leakage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_historical_race_results(db: DBSession) -> pd.DataFrame:
    """Load all historical completed race results from DB into a pandas DataFrame."""
    stmt = (
        select(
            Race.season,
            Race.round,
            Race.circuit,
            F1Session.race_id,
            SessionResult.driver_id,
            Driver.driver_code,
            Driver.team_id,
            SessionResult.position,
            SessionResult.lap_time,
        )
        .join(F1Session, F1Session.id == SessionResult.session_id)
        .join(Race, Race.id == F1Session.race_id)
        .join(Driver, Driver.id == SessionResult.driver_id)
        .where(F1Session.session_type == "RACE")
    )

    rows = db.execute(stmt).all()
    if not rows:
        return pd.DataFrame(columns=["season", "round", "circuit", "race_id", "driver_id", "driver_code", "team_id", "position", "lap_time"])

    df = pd.DataFrame(
        rows,
        columns=["season", "round", "circuit", "race_id", "driver_id", "driver_code", "team_id", "position", "lap_time"],
    )
    return df


def build_ml_dataset(
    db: Optional[DBSession] = None,
    output_path: Optional[Path] = None,
    stages: Optional[List[PredictionStage]] = None,
) -> pd.DataFrame:
    """Build leakage-safe ML dataset from PostgreSQL database."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        pipeline = FeaturePipeline()
        stages_to_build = stages or STAGE_ORDER

        # Load all historical race results for rolling form calculation
        historical_df = load_historical_race_results(db)

        # Load all races ordered chronologically
        races = db.scalars(select(Race).order_by(Race.season.asc(), Race.round.asc())).all()
        if not races:
            logger.warning("No races found in database to build dataset!")
            return pd.DataFrame()

        dataset_rows = []
        logger.info("Processing %d races across %d prediction stages...", len(races), len(stages_to_build))

        for race in races:
            # Load all weekend session results for this race
            sess_stmt = (
                select(
                    F1Session.session_type,
                    SessionResult.driver_id,
                    SessionResult.position,
                    SessionResult.lap_time,
                    Driver.driver_code,
                    Driver.team_id,
                )
                .join(SessionResult, SessionResult.session_id == F1Session.id)
                .join(Driver, Driver.id == SessionResult.driver_id)
                .where(F1Session.race_id == race.id)
            )

            weekend_rows = db.execute(sess_stmt).all()
            if not weekend_rows:
                continue

            weekend_df = pd.DataFrame(
                weekend_rows,
                columns=["session_type", "driver_id", "position", "lap_time", "driver_code", "team_id"],
            )

            # Identify drivers participating in this race weekend
            race_results = weekend_df[weekend_df["session_type"] == "RACE"]
            drivers_in_race = weekend_df[["driver_id", "driver_code", "team_id"]].drop_duplicates()

            # Target dictionary: driver_id -> finish_position
            target_pos_map = {}
            for _, r in race_results.iterrows():
                if pd.notna(r["position"]):
                    try:
                        target_pos_map[int(r["driver_id"])] = int(r["position"])
                    except (ValueError, TypeError):
                        pass

            for _, d_row in drivers_in_race.iterrows():
                driver_id = int(d_row["driver_id"])
                driver_code = str(d_row["driver_code"])
                team_id = int(d_row["team_id"]) if pd.notna(d_row["team_id"]) else None

                # Compute Targets from actual RACE session
                finish_pos = target_pos_map.get(driver_id, np.nan)
                win_val = 1 if (pd.notna(finish_pos) and finish_pos == 1) else 0
                podium_val = 1 if (pd.notna(finish_pos) and finish_pos <= 3) else 0
                top5_val = 1 if (pd.notna(finish_pos) and finish_pos <= 5) else 0

                # Generate row for each prediction stage
                for stage in stages_to_build:
                    features = pipeline.extract_features_for_row(
                        driver_id=driver_id,
                        team_id=team_id,
                        season=race.season,
                        round_num=race.round,
                        circuit_name=race.circuit,
                        stage=stage,
                        current_weekend_results_df=weekend_df,
                        historical_race_results_df=historical_df,
                    )

                    row_dict = {
                        "season": race.season,
                        "round": race.round,
                        "race_id": race.id,
                        "driver_id": driver_id,
                        "driver_code": driver_code,
                        "team_id": team_id,
                        "prediction_stage": stage.value,
                        **features,
                        TARGET_FINISH_POSITION: finish_pos,
                        TARGET_WIN: win_val,
                        TARGET_PODIUM: podium_val,
                        TARGET_TOP5: top5_val,
                    }
                    dataset_rows.append(row_dict)

        if not dataset_rows:
            logger.warning("No dataset rows generated.")
            return pd.DataFrame()

        df_dataset = pd.DataFrame(dataset_rows)

        # Validate no leakage
        is_valid, leakage_violations = validate_dataset_no_leakage(df_dataset)
        if not is_valid:
            logger.error("Leakage check failed with %d violations!", len(leakage_violations))
            raise ValueError(f"Dataset leakage validation failed: {leakage_violations[0]}")

        # Save to CSV if path specified
        save_path = output_path or DEFAULT_DATASET_CSV
        save_path.parent.mkdir(parents=True, exist_ok=True)
        df_dataset.to_csv(save_path, index=False)
        logger.info("Successfully generated dataset artifact: %s (%d rows, %d columns)", save_path, len(df_dataset), len(df_dataset.columns))

        return df_dataset

    finally:
        if close_db:
            db.close()


def main():
    parser = argparse.ArgumentParser(description="Build ML dataset from stored F1 PostgreSQL database.")
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_DATASET_CSV),
        help="Output CSV filepath",
    )
    args = parser.parse_args()

    out_path = Path(args.output)
    logger.info("Building ML dataset to %s...", out_path)
    df = build_ml_dataset(output_path=out_path)

    if not df.empty:
        print("\n=== Dataset Summary ===")
        print(f"Total Rows: {len(df)}")
        print(f"Total Columns: {len(df.columns)}")
        print(f"Seasons Included: {df['season'].unique().tolist()}")
        print(f"Races Count: {df['race_id'].nunique()}")
        print(f"Drivers Count: {df['driver_id'].nunique()}")
        print(f"Stages Represented: {df['prediction_stage'].unique().tolist()}")
        print(f"Output File: {out_path.resolve()}")
    else:
        print("Dataset generation resulted in 0 rows.")


if __name__ == "__main__":
    main()
