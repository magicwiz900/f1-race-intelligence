# F1 Race Intelligence - ML Data Pipeline & Feature Engineering

This module powers the stage-aware feature engineering, data leakage prevention, and dataset generation pipeline for **F1 Race Intelligence**.

---

## Architecture & Structure

```
ml/
├── __init__.py
├── stages.py             # Centralized PredictionStage enum & stage hierarchy
├── config.py             # Pipeline configuration, constants, and paths
├── features/
│   ├── __init__.py
│   ├── metadata.py       # Comprehensive metadata for all features
│   ├── pace_features.py  # Practice session pace (FP1, FP2, FP3) & lap gaps
│   ├── form_features.py  # Driver & Team historical rolling form
│   ├── qualifying_features.py # Qualifying grid position, lap time, pole gap
│   ├── circuit_features.py # Historical circuit performance
│   └── feature_pipeline.py # Orchestrator mapping stage availability & assembling feature matrix
├── datasets/
│   ├── __init__.py
│   └── build_dataset.py  # CLI script building dataset from PostgreSQL database
├── validation/
│   ├── __init__.py
│   └── leakage_checks.py # Automated data leakage verification functions
├── artifacts/            # Output folder for dataset artifacts (.csv)
│   └── .gitkeep
└── tests/                # Unit & leakage tests
    ├── __init__.py
    ├── conftest.py
    ├── test_features.py
    ├── test_dataset.py
    └── test_leakage.py
```

---

## Fundamental Unit of Data

The fundamental prediction unit is:

$$\text{One Driver} \times \text{One Race} \times \text{One Prediction Stage}$$

Each row in the dataset represents a driver's feature vector for a specific race event evaluated at a specific stage during the race weekend.

---

## Prediction Stages

Centralized enum defined in `ml/stages.py`:

1. `PRE_FP1`: Before Free Practice 1. Only historical form and circuit history available.
2. `POST_FP1`: After Free Practice 1. Includes FP1 pace and position.
3. `POST_FP2`: After Free Practice 2. Includes FP1 and FP2 pace and position.
4. `POST_FP3`: After Free Practice 3. Includes FP1, FP2, and FP3 pace and position.
5. `POST_QUALIFYING`: After Qualifying. Includes all practice sessions and Qualifying grid position/time.
6. `FINAL`: Pre-race state after all weekend sessions completed.

---

## Target Variables

Target variables are derived **strictly** from the actual `RACE` session results:
* `race_finish_position`: Driver's integer finishing position in the main race (1..N).
* `race_win`: Binary indicator (`1` if finish position is 1, else `0`).
* `race_podium`: Binary indicator (`1` if finish position $\le 3$, else `0`).
* `race_top5`: Binary indicator (`1` if finish position $\le 5$, else `0`).

> [!IMPORTANT]
> The target variables come from the actual `RACE` session and are **never** included in feature sets.

---

## Data Leakage Prevention Strategy

Data leakage is prevented through explicit, automated rules in `ml/features/feature_pipeline.py` and `ml/validation/leakage_checks.py`:
- **Stage Availability Masking**: Any feature associated with a session chronologically after the current prediction stage is set to `NaN` (masked).
- **Chronological Filtering**: Rolling historical form (driver/team) and circuit history features strictly compute metrics using races that occurred **before** the target race `(season, round)`.
- **Target Separation**: Race results are isolated in target columns and checked by automated tests (`test_leakage.py`).

---

## Chronological Validation Strategy

To evaluate ML models realistically, **random cross-validation MUST NOT be used**. F1 data has inherent temporal dependencies.
- **Training Set**: Historical seasons (e.g. earlier years / early season rounds).
- **Validation Set**: Mid-season rounds.
- **Test Set**: Recent rounds / final season races.

---

## Dataset Generation Command

To generate the dataset from the PostgreSQL database:

```bash
python -m ml.datasets.build_dataset --output ml/artifacts/f1_features_dataset.csv
```

---

## Running Tests

Run the ML unit test suite:

```bash
pytest ml/tests/
```

Run all backend and ML tests together:

```bash
pytest
```
