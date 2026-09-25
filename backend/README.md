# F1 Race Intelligence - Backend

The backend for **F1 Race Intelligence** provides a FastAPI REST API, PostgreSQL database models via SQLAlchemy 2.x, Alembic schema migrations, stage-aware prediction endpoints, and an F1 data ingestion layer.

---

## Architecture & Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application entrypoint & middleware
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
│   ├── services/        # Business logic & external integrations
│   │   ├── __init__.py
│   │   └── f1_data/     # Ingestion layer modules
│   │       ├── __init__.py
│   │       ├── jolpica_client.py # HTTP client for Jolpica F1 API
│   │       ├── fastf1_service.py # FastF1 detailed session data service abstraction
│   │       ├── transformers.py   # Raw API response transformers
│   │       └── importer.py       # Idempotent DB data ingestion pipeline
│   └── api/             # FastAPI REST endpoints
│       ├── __init__.py
│       ├── deps.py      # Database & API Key dependency injection
│       ├── health.py    # Health check endpoint
│       ├── races.py     # Race calendar, session, and results API
│       ├── drivers.py   # Driver metadata API
│       ├── teams.py     # Team/Constructor API
│       ├── sessions.py  # Session details & timing API
│       ├── predictions.py # Stage-aware prediction API
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
│   ├── test_health.py         # Health check API tests
│   ├── test_database.py       # Database schema & ORM relationship tests
│   ├── test_jolpica_client.py # Jolpica client mocked unit tests
│   ├── test_f1_importer.py    # Importer idempotency & DB mapping tests
│   └── test_api.py            # Comprehensive REST API integration tests
├── alembic.ini          # Alembic migration configuration
├── .env.example         # Environment variable template
├── requirements.txt     # Python dependencies
└── README.md
```

---

## Quickstart Setup

### 1. Create Virtual Environment

From the `backend/` directory:

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## REST API Endpoints

All endpoints are registered under `/api`. Interactive documentation is automatically generated at `/docs`.

### Health & Security
* `GET /api/health`: Health check endpoint.
* `GET /api/protected-demo`: Security demo endpoint protected by `X-API-Key` header dependency (requires `API_KEY` when set in environment).

### Races
* `GET /api/races?season=2025&limit=100&offset=0`: List races chronologically by season and round.
* `GET /api/races/{race_id}`: Single race detail (returns 404 if not found).
* `GET /api/races/{race_id}/sessions`: Sessions (`FP1`, `FP2`, `FP3`, `QUALIFYING`, `RACE`) for a given race.
* `GET /api/races/{race_id}/results?session_type=RACE`: Session results with joined driver and team objects.
* `GET /api/races/{race_id}/predictions?stage=POST_FP2`: Stage-aware model predictions for a race. Returns `[]` if none exist yet.

### Drivers
* `GET /api/drivers?season=2025`: List drivers with associated team details (optional season filter).
* `GET /api/drivers/{driver_id}`: Single driver detail with team information.

### Teams
* `GET /api/teams`: List all F1 constructor teams.
* `GET /api/teams/{team_id}`: Single team detail including driver list.

### Sessions
* `GET /api/sessions/{session_id}`: Detailed session information including race context and driver timing results.

### Predictions
* `GET /api/predictions?race_id=1&stage=POST_QUALIFYING`: Query prediction records across races and stages.
* `GET /api/predictions/stages`: List supported weekend prediction stages (`PRE_FP1`, `POST_FP1`, `POST_FP2`, `POST_FP3`, `POST_QUALIFYING`, `FINAL`).

---

## Security & API-Key Configuration

Protected endpoints consume the reusable dependency `verify_api_key` in `app/api/deps.py`.
- **Environment Variable**: Set `API_KEY=your_secret_key` in `.env`.
- **Header**: Pass `X-API-Key: your_secret_key` in HTTP requests.

Example request:
```bash
curl -H "X-API-Key: secret_key" http://127.0.0.1:8000/api/protected-demo
```

---

## Data Ingestion Layer

### Data Sources
1. **Primary Structured Data**: Jolpica F1 API (`https://api.jolpi.ca/ergast/f1`) for seasons, race calendars, drivers, constructors, and race results.
2. **Detailed Session Data**: FastF1 integration abstraction (`FastF1Service`) prepared for FP1/FP2/FP3/Qualifying/Race lap times, sector times, tyre compounds, and stints.

### How to Run Ingestion

```bash
# Ingest an F1 season (default 2025)
python -m scripts.ingest_f1_data --season 2025
```

---

## Database Setup & PostgreSQL Configuration

### Starting PostgreSQL via Docker Compose

```bash
docker-compose up -d postgres
```

### Running Database Migrations (Alembic)

```bash
alembic upgrade head
alembic current
```

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
pytest
```
