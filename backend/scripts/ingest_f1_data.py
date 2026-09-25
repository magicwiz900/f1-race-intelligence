import argparse
import logging
import sys

from app.database import SessionLocal
from app.services.f1_data import F1DataImporter, JolpicaClient

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest F1 season data into PostgreSQL database.")
    parser.add_argument(
        "--season",
        type=int,
        default=2025,
        help="F1 Season year to ingest (e.g. 2025 or 2024). Default is 2025.",
    )
    args = parser.parse_args()

    season = args.season
    logger.info("Fetching season %d...", season)

    db = SessionLocal()
    client = JolpicaClient()
    importer = F1DataImporter(db=db, client=client)

    try:
        stats = importer.import_season(season)
        print(f"Found {stats['races']} races")
        print(f"Imported/updated {stats['teams']} teams")
        print(f"Imported/updated {stats['drivers']} drivers")
        print(f"Imported/updated {stats['races']} races")
        print("Ingestion completed successfully")
    except Exception as e:
        logger.error("Data ingestion failed for season %d: %s", season, e, exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
