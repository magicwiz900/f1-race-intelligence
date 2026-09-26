# F1 Race Intelligence

## Project Overview
**F1 Race Intelligence** is a full-stack predictive telemetry and race intelligence platform designed to analyze Formula 1 race-weekend data and dynamically predict race outcomes as each weekend session unfolds.

The system dynamically updates driver race win probabilities (raw and race-share normalized), podium probabilities, top-5 finish likelihoods, and predicted finishing positions across distinct race-weekend stages:
1. `PRE_FP1`
2. `POST_FP1`
3. `POST_FP2`
4. `POST_FP3`
5. `POST_QUALIFYING`

---

## System Architecture

```text
F1 Data Sources (Jolpica F1 API / FastF1 Abstraction)
                        ↓
         Data Ingestion & Ingestion Pipeline
                        ↓
            PostgreSQL Database (SQLAlchemy 2.x)
                        ↓
     Feature Pipeline & Leakage Validation (ML)
                        ↓
     Trained Model Artifacts (.joblib Pipelines)
                        ↓
  Prediction Service Layer & Relative Race Normalization
                        ↓
             FastAPI REST API (/api/races/...)
                        ↓
  F1 Motorsport Command Center Dashboard (Frontend)
```

---

## Technology Stack

* **Frontend**: HTML5, CSS3 (Custom Carbon Motorsport Design System), Modern JavaScript, Lucide Icons
* **Backend**: Python 3.14, FastAPI, SQLAlchemy 2.x, Pydantic, Alembic
* **Database**: PostgreSQL 16 (via Docker Compose / SQLite in-memory test suite)
* **Machine Learning**: scikit-learn (LogisticRegression, RandomForestRegressor), pandas, numpy, joblib
* **Data Sources**: Jolpica Ergast F1 API, FastF1 session data integration layer

---

## Folder Structure

```text
f1-race-intelligence/
├── frontend/             # Motorsport Command Center UI Dashboard
│   ├── index.html        # Main HTML5 application markup
│   ├── styles.css        # Custom F1 motorsport dark theme & design system
│   ├── app.js            # State management, API client, & timing board logic
│   └── README.md
├── backend/              # FastAPI REST API & Database Services
│   ├── app/
│   │   ├── api/          # REST route handlers (races, drivers, teams, sessions, predictions)
│   │   ├── models/       # SQLAlchemy 2.x ORM models
│   │   ├── schemas/      # Pydantic response models
│   │   └── services/
│   │       ├── f1_data/  # Jolpica API client & idempotent data importer
│   │       └── prediction_service/ # ModelLoader, FeatureAdapter & PredictionService
│   ├── migrations/       # Alembic schema migrations
│   ├── tests/            # Backend unit & integration test suite
│   └── README.md
├── ml/                   # Machine Learning Pipeline & Training Layer
│   ├── features/         # Feature engineering & leakage-safe FeaturePipeline
│   ├── datasets/         # Dataset generation scripts
│   ├── training/         # Trainer, model training CLI, & prediction sanity checks
│   ├── validation/       # Data leakage checkers
│   ├── artifacts/        # Trained .joblib models, metrics, calibration & metadata
│   ├── tests/            # Feature, leakage, training & analysis tests
│   └── README.md
├── data/                 # Raw and processed F1 dataset storage
├── docs/                 # System architecture & design documentation
├── pytest.ini            # Root pytest configuration
├── docker-compose.yml    # PostgreSQL Docker Compose configuration
└── README.md
```

---

## Running the Application

### 1. Start FastAPI Backend & Prediction Server

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

### 2. Access Web Applications

* **Frontend Dashboard**: [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard) or [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **API Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

### 3. Run Test Suite

```powershell
pytest -v
```

All 67 test suites (backend, database, API, ML features, leakage validation, prediction service) execute and pass in under 3 seconds.