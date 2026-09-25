from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DATASET_CSV = ARTIFACTS_DIR / "f1_features_dataset.csv"

# Historical form rolling window sizes (number of prior races)
ROLLING_WINDOW_RACES = 5

# F1 Championship Points system (Top 10 finishes)
POINTS_MAP = {
    1: 25,
    2: 18,
    3: 15,
    4: 12,
    5: 10,
    6: 8,
    7: 6,
    8: 4,
    9: 2,
    10: 1,
}

# Primary and Secondary Target column names
TARGET_FINISH_POSITION = "race_finish_position"
TARGET_WIN = "race_win"
TARGET_PODIUM = "race_podium"
TARGET_TOP5 = "race_top5"

TARGET_COLUMNS = [
    TARGET_FINISH_POSITION,
    TARGET_WIN,
    TARGET_PODIUM,
    TARGET_TOP5,
]

ID_COLUMNS = [
    "season",
    "round",
    "race_id",
    "driver_id",
    "driver_code",
    "team_id",
    "prediction_stage",
]
