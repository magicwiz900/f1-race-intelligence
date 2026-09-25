# F1 Race Intelligence - ML Data Pipeline & Training Layer

This module powers the stage-aware feature engineering, data leakage prevention, chronological dataset splitting, model training, calibration evaluation, and explainability layer for **F1 Race Intelligence**.

---

## Architecture & Structure

```
ml/
├── __init__.py
├── stages.py             # Centralized PredictionStage enum & stage hierarchy
├── config.py             # Pipeline configuration, constants, and paths
├── data_split.py         # Chronological race boundary dataset splitting utility
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
├── training/
│   ├── __init__.py
│   ├── trainer.py        # Model training, evaluation, and calibration logic
│   └── train_models.py   # CLI entrypoint for training all models
├── validation/
│   ├── __init__.py
│   └── leakage_checks.py # Automated data leakage verification functions
├── artifacts/            # Generated model weights, metrics, and metadata
│   ├── models/           # .joblib trained model pipelines
│   ├── metrics/          # model_metrics.json
│   ├── calibration/      # calibration_data.json
│   └── metadata/         # model_metadata.json & feature_metadata.json
└── tests/                # Unit, leakage, and training tests
    ├── __init__.py
    ├── conftest.py
    ├── test_features.py
    ├── test_dataset.py
    ├── test_leakage.py
    └── test_training.py
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
4. `POST_QUALIFYING`: After Qualifying. Includes all practice sessions and Qualifying grid position/time.
5. `FINAL`: Pre-race state after all weekend sessions completed.

---

## Models & Targets

1. **Win Probability Model**: `LogisticRegression(class_weight='balanced')` predicting `race_win` (1/0). Evaluated using **Log Loss** and **Brier Score**.
2. **Finish Position Model**: `RandomForestRegressor(n_estimators=100, max_depth=6)` predicting `race_finish_position` (1..20). Evaluated using **MAE** and **RMSE**.
3. **Podium Model**: `LogisticRegression` predicting `race_podium` (1/0). Evaluated using Log Loss, Brier Score, and ROC-AUC.
4. **Top 5 Model**: `LogisticRegression` predicting `race_top5` (1/0). Evaluated using Log Loss, Brier Score, and ROC-AUC.

---

## Data Leakage Prevention & Chronological Splitting

- **Target Separation**: Target columns (`race_finish_position`, `race_win`, `race_podium`, `race_top5`) are strictly isolated from the feature matrix `X`.
- **Race Boundary Splitting**: Splitting is performed chronologically by race boundaries (`season`, `round`). Complete races remain together; no race is split across training and testing partitions.
  - **Train**: Rounds 1–14 (14 races, 1,674 rows)
  - **Validation**: Rounds 15–19 (5 races, 600 rows)
  - **Test**: Rounds 20–24 (5 races, 600 rows)

---

## Running Dataset Generation & Model Training

### 1. Build Dataset
```bash
python -m ml.datasets.build_dataset --output ml/artifacts/f1_features_dataset.csv
```

### 2. Train & Evaluate Models
```bash
python -m ml.training.train_models --dataset ml/artifacts/f1_features_dataset.csv
```

---

## Running Tests

Run the full test suite (backend + ML):

```bash
pytest
```
