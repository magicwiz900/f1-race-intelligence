# F1 Race Intelligence - ML Data Pipeline & Training Layer

This module powers the stage-aware feature engineering, data leakage prevention, chronological dataset splitting, model training, calibration evaluation, stage progression analysis, and explainability layer for **F1 Race Intelligence**.

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
│   ├── train_models.py   # CLI entrypoint for training all models
│   └── analyze_predictions.py # CLI script for stage-wise validation & sanity checks
├── validation/
│   ├── __init__.py
│   └── leakage_checks.py # Automated data leakage verification functions
├── artifacts/            # Generated model weights, metrics, and metadata
│   ├── models/           # .joblib trained model pipelines
│   ├── metrics/          # model_metrics.json, stage_metrics.json, winner_probability_trajectories.json
│   ├── calibration/      # calibration_data.json, calibration_10bin_data.json
│   └── metadata/         # model_metadata.json & feature_metadata.json
└── tests/                # Unit, leakage, training, and analysis tests
    ├── __init__.py
    ├── conftest.py
    ├── test_features.py
    ├── test_dataset.py
    ├── test_leakage.py
    ├── test_training.py
    └── test_analysis.py
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
6. `FINAL`: Pre-race state after all weekend sessions completed (excluded from prediction REST API endpoints to avoid exposing misleading post-race predictions).

> **API Integration**: Loaded by `backend/app/services/prediction_service` to serve REST predictions at `/api/races/{race_id}/predictions`. Provides both raw Logistic Regression outputs (`raw_win_probability`) and normalized race share probabilities (`race_share_probability`).

---

## Models & Targets

1. **Win Probability Model**: `LogisticRegression(class_weight='balanced')` predicting `race_win` (1/0). Evaluated using **Log Loss** and **Brier Score**.
2. **Finish Position Model**: `RandomForestRegressor(n_estimators=100, max_depth=6)` predicting `race_finish_position` (1..20). Evaluated using **MAE** and **RMSE**.
3. **Podium Model**: `LogisticRegression` predicting `race_podium` (1/0). Evaluated using Log Loss, Brier Score, and ROC-AUC.
4. **Top 5 Model**: `LogisticRegression` predicting `race_top5` (1/0). Evaluated using Log Loss, Brier Score, and ROC-AUC.

---

## Model Sanity & Stage Analysis

A comprehensive validation and sanity check was performed on the chronological test split (2025 season rounds 20–24, 600 rows):

### 1. Stage-Wise Prediction Behavior
* Evaluated pre-race stages (`PRE_FP1` through `POST_QUALIFYING`).
* **Log Loss**: `0.4099` across stages.
* **Brier Score**: `0.1327` across stages.
* **Avg Predicted Win Probability of Eventual Winner**: `85.1%` (drivers with high historical form e.g. Verstappen/Norris were assigned high probabilities).

### 2. Race Probability Sum Behavior
* **Mean Probability Sum per Race**: `6.0051` (min: `5.8379`, max: `6.1011`).
* **Finding & Architecture Note**: Because independent binary `LogisticRegression` models evaluate each driver's binary win likelihood independently with `class_weight='balanced'`, predicted probabilities across ~20 drivers sum to ~6.0 per race instead of 1.0. Softmax or post-processing normalization will be applied at the API presentation layer when displaying race-wide probabilities to frontend users.

### 3. Calibration Analysis (10 Bins)
* Evaluated across 10 probability bins `0–10%` to `90–100%`.
* **Single-Season Limitation**: Because the current dataset only contains 2025 season data (5.01% positive win rate), higher probability bins contain small sample sizes. Calibration findings are preliminary.

### 4. Finish Position Model Sanity Check
* **MAE**: `4.8565` positions.
* **RMSE**: `6.2633` positions.
* **Predicted Position Range**: `2.72` to `17.92`.
* **Out-of-Bounds Count**: `0` (All predictions fall strictly within valid grid bounds 1 to 20).
* **Sanity Status**: `VALID`.

---

## Commands

### 1. Build Dataset
```bash
python -m ml.datasets.build_dataset --output ml/artifacts/f1_features_dataset.csv
```

### 2. Train & Evaluate Models
```bash
python -m ml.training.train_models --dataset ml/artifacts/f1_features_dataset.csv
```

### 3. Run Stage Prediction Analysis
```bash
python -m ml.training.analyze_predictions --dataset ml/artifacts/f1_features_dataset.csv
```

---

## Running Tests

Run the full test suite (backend + ML):

```bash
pytest
```
