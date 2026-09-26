import argparse
import logging
import sys

from app.database import SessionLocal
from app.services.f1_data.fastf1_enricher import FastF1Enricher

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Enrich F1 season with real FastF1 FP1/FP2/FP3/Qualifying session timings.")
    parser.add_argument(
        "--season",
        type=int,
        default=2025,
        help="F1 Season year to enrich (e.g. 2025). Default is 2025.",
    )
    args = parser.parse_args()

    season = args.season
    logger.info("Enriching season %d with FastF1 session data...", season)

    db = SessionLocal()
    enricher = FastF1Enricher(db=db)

    try:
        stats = enricher.enrich_season(season)
        print(f"Processed {stats['races_processed']} races for season {season}")
        print(f"Enriched {stats['sessions_enriched']} sessions with FastF1 timing data")
        print(f"Stored/updated {stats['session_results_stored']} session results")
        print("FastF1 enrichment completed successfully")
    except Exception as e:
        logger.error("FastF1 enrichment failed for season %d: %s", season, e, exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
