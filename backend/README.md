# F1 Race Intelligence - Backend

The backend for **F1 Race Intelligence** provides a FastAPI REST API, PostgreSQL database models via SQLAlchemy 2.x, Alembic schema migrations, stage-aware prediction endpoints, a production prediction service layer loading trained ML artifacts (`.joblib`), and an F1 data ingestion layer.

---

## Architecture & Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application entrypoint, model preloading & middleware
│   ├── config.py        # Environment settings via pydantic-settings
│   ├── database.py      # SQLAlchemy engine, sessionmaker & Base
│   ├── models/          # SQLAlchemy 2.x ORM models
│   │   ├── __init__.py
│   │   ├── team.py
│   │   ├── driver.py
│   │   ├── race.py
│   │   ├── session.py
│   │   ├── session_result.py
│   │   └── prediction.py
│   ├── schemas/         # Pydantic response models
│   │   ├── __init__.py
│   │   ├── team.py
│   │   ├── driver.py
│   │   ├── race.py
│   │   ├── session.py
│   │   └── prediction.py
│   ├── services/        # Business logic & prediction service layer
│   │   ├── __init__.py
│   │   ├── f1_data/     # Ingestion layer modules
│   │   │   ├── __init__.py
│   │   │   ├── jolpica_client.py # HTTP client for Jolpica F1 API
│   │   │   ├── fastf1_service.py # FastF1 detailed session data service abstraction
│   │   │   ├── transformers.py   # Raw API response transformers
│   │   │   └── importer.py       # Idempotent DB data ingestion pipeline
│   │   └── prediction_service/   # ML Prediction Service Layer (Step 8)
│   │       ├── __init__.py
│   │       ├── model_loader.py   # Singleton joblib model loader
│   │       ├── feature_adapter.py # Database to FeaturePipeline adapter
│   │       └── predictor.py      # Prediction orchestrator & relative race normalization
│   └── api/             # FastAPI REST endpoints
│       ├── __init__.py
│       ├── deps.py      # Database & API Key dependency injection
│       ├── health.py    # Health check endpoint
│       ├── races.py     # Race calendar, session, results, and ML predictions API
│       ├── drivers.py   # Driver metadata API
│       ├── teams.py     # Team/Constructor API
│       ├── sessions.py  # Session details & timing API
│       ├── predictions.py # Stage-aware prediction query API
│       └── protected.py # API-Key security demo endpoint
├── scripts/
│   ├── __init__.py
│   └── ingest_f1_data.py # CLI script for ingesting an F1 season
├── migrations/          # Alembic database migration scripts
│   ├── versions/
│   │   └── 0001_initial_schema.py
│   ├── env.py
│   └── script.py.mako
├── tests/
│   ├── conftest.py            # Shared test fixtures for API tests
│   ├── test_health.py         # Health check API tests
│   ├── test_database.py       # Database schema & ORM relationship tests
│   ├── test_jolpica_client.py # Jolpica client mocked unit tests
│   ├── test_f1_importer.py    # Importer idempotency & DB mapping tests
│   ├── test_api.py            # REST API integration tests
│   ├── test_prediction_service.py # Prediction service & model loading unit tests
│   └── test_prediction_api.py # Prediction REST API endpoint integration tests
├── alembic.ini          # Alembic migration configuration
├── .env.example         # Environment variable template
├── requirements.txt     # Python dependencies
└── README.md
```

---

## Prediction Service & ML Integration (Step 8)

The Prediction Service connects:

```text
PostgreSQL / Feature Pipeline
        ↓
ML Models (.joblib)
        ↓
PredictionService / ModelLoader / FeatureAdapter
        ↓
FastAPI REST API
```

### Loaded Model Artifacts
* `win_probability_model.joblib`: Binary Logistic Regression model predicting race win likelihood.
* `finish_position_model.joblib`: Random Forest Regressor predicting expected finish position ($1.0 - 20.0$).
* `podium_model.joblib`: Binary classification model predicting top-3 finish probability.
* `top5_model.joblib`: Binary classification model predicting top-5 finish probability.

### Supported Prediction Stages
* `PRE_FP1`
* `POST_FP1`
* `POST_FP2`
* `POST_FP3`
* `POST_QUALIFYING`

> **Note on `FINAL` Stage**: `FINAL` is strictly excluded from prediction endpoints to avoid exposing misleading post-race state predictions.

### Raw vs Race-Share Win Probability
* **`raw_win_probability`**: Unmodified binary Logistic Regression model output per driver ($\sum P_{\text{raw}} \approx 6.0$).
* **`race_share_probability`**: Race-level relative normalized presentation probability ($\frac{P_{\text{raw}, i}}{\sum_j P_{\text{raw}, j}}$) ensuring $\sum P_{\text{share}} \approx 1.0$ for all drivers competing in a race.

### FastF1 Real Session Data Enrichment (Step 11)
FastF1 enriches PostgreSQL with real `FP1`, `FP2`, `FP3`, and `QUALIFYING` session timings, sector times, tyre compounds, and lap counts.

To run FastF1 enrichment:
```bash
python -m scripts.enrich_fastf1_data --season 2025
```

Every prediction API response includes a `data_availability` transparency metadata object dynamically indicating active session data feeds:
```json
"data_availability": {
  "historical_form": true,
  "fp1": true,
  "fp2": true,
  "fp3": true,
  "qualifying": true
}
```

---

## REST API Endpoints

All endpoints are registered under `/api`. Interactive documentation is automatically generated at `/docs`.

### Health & Security
* `GET /api/health`: Health check endpoint.
* `GET /api/protected-demo`: Security demo endpoint protected by `X-API-Key` header.

### Predictions (Step 8)
* `GET /api/races/{race_id}/predictions`: Live ML prediction response for a race. Optional query parameter `stage` (defaults to `POST_QUALIFYING`).
* `GET /api/races/{race_id}/predictions/{stage}`: Stage-specific predictions (e.g. `POST_FP3`).

Response Example:
```json
{
  "race_id": 24,
  "season": 2025,
  "round": 1,
  "race_name": "Australian Grand Prix",
  "stage": "POST_QUALIFYING",
  "predictions": [
    {
      "driver_id": 1,
      "driver_code": "VER",
      "driver_name": "Max Verstappen",
      "team_id": 1,
      "team_name": "Red Bull Racing",
      "raw_win_probability": 0.7215,
      "race_share_probability": 0.3412,
      "podium_probability": 0.8105,
      "top5_probability": 0.9410,
      "predicted_finish_position": 1.85
    }
  ],
  "data_availability": {
    "historical_form": true,
    "fp1": false,
    "fp2": false,
    "fp3": false,
    "qualifying": false
  }
}
```

### Races
* `GET /api/races?season=2025&limit=100&offset=0`: List races chronologically by season and round.
* `GET /api/races/{race_id}`: Single race detail (returns 404 if not found).
* `GET /api/races/{race_id}/sessions`: Sessions (`FP1`, `FP2`, `FP3`, `QUALIFYING`, `RACE`) for a given race.
* `GET /api/races/{race_id}/results?session_type=RACE`: Session results with joined driver and team objects.

### Drivers
* `GET /api/drivers?season=2025`: List drivers with associated team details.
* `GET /api/drivers/{driver_id}`: Single driver detail with team information.

### Teams
* `GET /api/teams`: List all F1 constructor teams.
* `GET /api/teams/{team_id}`: Single team detail including driver list.

### Sessions
* `GET /api/sessions/{session_id}`: Detailed session information including race context and driver timing results.

### Predictions Metadata
* `GET /api/predictions/stages`: List supported prediction stages (`PRE_FP1`, `POST_FP1`, `POST_FP2`, `POST_FP3`, `POST_QUALIFYING`).

---

## Running the Development Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc API Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## Running Tests

Run the full backend test suite:

```bash
pytest -v
```
